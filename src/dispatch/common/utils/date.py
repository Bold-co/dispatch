import datetime
import pytz


def date_to_tz(date: datetime):
    timezone = pytz.utc
    d_aware = timezone.localize(date)
    local_time = d_aware.astimezone(pytz.timezone("America/Bogota"))
    return local_time.strftime("%d/%m/%Y %H:%M:%S")


def date_diff_in_seconds(end_date: datetime, start_date: datetime):
    timedelta = end_date - start_date
    return timedelta.days * 24 * 3600 + timedelta.seconds


def dhms_from_seconds(seconds: int):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return days, hours, minutes


def date_diff(end_date: datetime, start_date: datetime) -> str:
    return "%d days, %d hours, %d min" % dhms_from_seconds(date_diff_in_seconds(end_date, start_date))
