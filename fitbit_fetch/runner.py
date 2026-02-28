"""Orchestration flows for startup, bulk update, and scheduled updates."""


def run_startup_or_bulk_update(
    *,
    auto_date_range,
    start_date,
    end_date,
    start_date_str,
    end_date_str,
    schedule_module,
    logger,
    get_new_access_token,
    client_id,
    client_secret,
    build_date_list,
    get_intraday_data_limit_1d,
    get_daily_data_limit_30d,
    get_daily_data_limit_100d,
    get_daily_data_limit_365d,
    get_daily_data_limit_none,
    get_battery_level,
    fetch_latest_activities,
    write_points_to_influxdb,
    write_and_reset_records,
    yield_dates_with_gap,
    get_collected_records,
    set_collected_records,
):
    if auto_date_range:
        date_list = build_date_list(start_date, end_date)
        if len(date_list) > 3:
            logger.warn(
                "Auto schedule update is not meant for more than 3 days at a time, "
                "please consider lowering the auto_update_date_range variable to aviod rate limit hit!"
            )
        for date_str in date_list:
            get_intraday_data_limit_1d(
                date_str,
                [("heart", "HeartRate_Intraday", "1sec"), ("steps", "Steps_Intraday", "1min")],
            )
        get_daily_data_limit_30d(start_date_str, end_date_str)
        get_daily_data_limit_100d(start_date_str, end_date_str)
        get_daily_data_limit_365d(start_date_str, end_date_str)
        get_daily_data_limit_none(start_date_str, end_date_str)
        get_battery_level()
        fetch_latest_activities(end_date_str)
        set_collected_records(write_and_reset_records(write_points_to_influxdb, get_collected_records()))
    else:
        schedule_module.every(1).hours.do(lambda: get_new_access_token(client_id, client_secret))

        date_list = build_date_list(start_date, end_date)

        def do_bulk_update(funcname, range_start_date, range_end_date):
            funcname(range_start_date, range_end_date)
            schedule_module.run_pending()
            set_collected_records(write_and_reset_records(write_points_to_influxdb, get_collected_records()))

        fetch_latest_activities(date_list[-1])
        write_points_to_influxdb(get_collected_records())
        do_bulk_update(get_daily_data_limit_none, date_list[0], date_list[-1])
        for date_range in yield_dates_with_gap(date_list, 360):
            do_bulk_update(get_daily_data_limit_365d, date_range[0], date_range[1])
        for date_range in yield_dates_with_gap(date_list, 98):
            do_bulk_update(get_daily_data_limit_100d, date_range[0], date_range[1])
        for date_range in yield_dates_with_gap(date_list, 28):
            do_bulk_update(get_daily_data_limit_30d, date_range[0], date_range[1])
        for single_day in date_list:
            do_bulk_update(
                get_intraday_data_limit_1d,
                single_day,
                [("heart", "HeartRate_Intraday", "1sec"), ("steps", "Steps_Intraday", "1min")],
            )

        logger.info("Success : Bulk update complete for " + start_date_str + " to " + end_date_str)
        print("Bulk update complete!")


def run_scheduled_auto_update_loop(
    *,
    schedule_module,
    get_new_access_token,
    client_id,
    client_secret,
    get_intraday_data_limit_1d,
    get_battery_level,
    get_daily_data_limit_30d,
    get_daily_data_limit_100d,
    get_daily_data_limit_365d,
    get_daily_data_limit_none,
    fetch_latest_activities,
    get_start_date_str,
    get_end_date_str,
    datetime_cls,
    timedelta_cls,
    get_collected_records,
    set_collected_records,
    write_points_to_influxdb,
    write_and_reset_records,
    update_working_dates,
    time_module,
):
    schedule_module.every(1).hours.do(lambda: get_new_access_token(client_id, client_secret))
    schedule_module.every(3).minutes.do(
        lambda: get_intraday_data_limit_1d(
            get_end_date_str(),
            [("heart", "HeartRate_Intraday", "1sec"), ("steps", "Steps_Intraday", "1min")],
        )
    )
    schedule_module.every(1).hours.do(
        lambda: get_intraday_data_limit_1d(
            (datetime_cls.strptime(get_end_date_str(), "%Y-%m-%d") - timedelta_cls(days=1)).strftime("%Y-%m-%d"),
            [("heart", "HeartRate_Intraday", "1sec"), ("steps", "Steps_Intraday", "1min")],
        )
    )
    schedule_module.every(20).minutes.do(get_battery_level)
    schedule_module.every(3).hours.do(lambda: get_daily_data_limit_30d(get_start_date_str(), get_end_date_str()))
    schedule_module.every(4).hours.do(lambda: get_daily_data_limit_100d(get_start_date_str(), get_end_date_str()))
    schedule_module.every(6).hours.do(lambda: get_daily_data_limit_365d(get_start_date_str(), get_end_date_str()))
    schedule_module.every(6).hours.do(lambda: get_daily_data_limit_none(get_start_date_str(), get_end_date_str()))
    schedule_module.every(1).hours.do(lambda: fetch_latest_activities(get_end_date_str()))

    while True:
        schedule_module.run_pending()
        if len(get_collected_records()) != 0:
            set_collected_records(write_and_reset_records(write_points_to_influxdb, get_collected_records()))
        time_module.sleep(30)
        update_working_dates()
