import datetime
import pytz


def date_to_tz(date: datetime):
    timezone = pytz.utc
    d_aware = timezone.localize(date)
    local_time = d_aware.astimezone(pytz.timezone("America/Bogota"))
    return local_time.strftime("%d/%m/%Y, %H:%M:%S")
