"""Sensor to indicate whether the current day is bin collection day in Auckland."""
import datetime
import logging

from bs4 import BeautifulSoup
from dateutil.parser import parse
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.components.rest.sensor import RestData
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = datetime.timedelta(hours=1)
_LOGGER = logging.getLogger(__name__)

CONF_LOC = "location"
CONF_ALERT_HOURS = "alert_hours_before"

DEFAULT_LOC = "12344022656"
DEFAULT_NAME = "Auckland Bin Collection"
DEFAULT_ALERT_HOURS = 5

ATTR_LOCATION = "location"
ATTR_ALERT_HOURS = "alert_hours_before"
ATTR_NEXT_COLLECT_DATE = "next_collect_date"
ATTR_NEXT_COLLECT_DATE_2 = "next2_collect_date"
ATTR_IS_RUBBISH = "next_is_rubbish"
ATTR_IS_RECYCLE = "next_is_recycle"
ATTR_IS_RUBBISH_2 = "next2_is_rubbish"
ATTR_IS_RECYCLE_2 = "next2_is_recycle"
ATTR_LAST_UPDATE = "last_update"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LOC): cv.string,
        vol.Optional(CONF_ALERT_HOURS, default=DEFAULT_ALERT_HOURS): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Auckland Bin Day sensor."""
    loc = config[CONF_LOC]
    alert_hour = config[CONF_ALERT_HOURS]
    sensor_name = config[CONF_NAME]
    method = "GET"
    resource = (
        "https://www.aucklandcouncil.govt.nz/rubbish-recycling/rubbish-recycling-collections/Pages/collection-day-detail.aspx?an="
        + loc
    )  # 12344022656"
    auth = None
    headers = None
    payload = None
    verify_ssl = True
    rest = RestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        raise PlatformNotReady

    add_entities([AucklandBinDay(rest, loc, alert_hour, sensor_name)], True)


def fetch_data(name, rest):
    """Fetch data IO shouldn't be here."""
    rest.update()
    if rest.data is None:
        _LOGGER.error("Unable to retrieve data for %s", name)
        return

    soup = BeautifulSoup(rest.data, "html.parser")
    box = soup.find(
        id="ctl00_SPWebPartManager1_g_dfe289d2_6a8a_414d_a384_fc25a0db9a6d_ctl00_pnlHouseholdBlock"
    )

    date_box = box.find_all("span", attrs={"class": "m-r-1"})

    ret = []
    for date_line in date_box:
        date_str = date_line.text.strip()
        # date_str = "3 May"
        dt_obj = parse(date_str)

        if (
            dt_obj.date() < datetime.date.today()
        ):  # if date < today date, this is next year
            dt_obj = dt_obj.replace(year=dt_obj.year + 1)

        collect_line = date_line.parent.find_all("span", attrs={"class": "sr-only"})
        collect_list = []
        for collect_item in collect_line:
            collect_list.append(collect_item.text.strip())

        result = {
            "DateString": date_str,
            "Date": dt_obj.date(),
            "Collect": collect_list,
        }
        ret.append(result)

    return ret


class AucklandBinDay(BinarySensorEntity):
    """Implementation of Auckland Waste Collection sensor."""

    def __init__(self, rest, loc, hours, name):
        """Initialize the Auckland Waste Collection Sensor."""
        self.rest = rest
        self._name = name
        self._loc = loc
        self._hours = hours
        self._state = None
        self._next_date = None
        self._next_date_2 = None
        self._is_rubbish = None
        self._is_rubbish_2 = None
        self._is_recycle = None
        self._is_recycle_2 = None
        self._last_update = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return the attributes of the entity."""
        return {
            ATTR_LOCATION: self._loc,
            ATTR_ALERT_HOURS: self._hours,
            ATTR_NEXT_COLLECT_DATE: self._next_date,
            ATTR_NEXT_COLLECT_DATE_2: self._next_date_2,
            ATTR_IS_RUBBISH: self._is_rubbish,
            ATTR_IS_RECYCLE: self._is_recycle,
            ATTR_IS_RUBBISH_2: self._is_rubbish_2,
            ATTR_IS_RECYCLE_2: self._is_recycle_2,
            ATTR_LAST_UPDATE: self._last_update,
        }

    async def async_update(self):
        """Fetch data from the website."""
        date_string = []
        date_obj = []
        collect = []
        self._state = "off"
        self._next_date = None
        self._next_date_2 = None
        self._is_rubbish = "No"
        self._is_recycle = "No"
        self._is_rubbish_2 = "No"
        self._is_recycle_2 = "No"
        self._last_update = datetime.datetime.now()

        # data = fetch_data(self._loc)
        data = fetch_data(self._name, self.rest)

        for item in data:
            collect_dt = datetime.datetime.combine(item["Date"], datetime.time.min)
            alert_dt = datetime.datetime.now() + datetime.timedelta(hours=self._hours)

            if alert_dt >= collect_dt:
                self._state = "on"

            date_obj.append(item["Date"])
            if item["Date"] == datetime.date.today():
                date_string.append("Today")
            elif item["Date"] == datetime.date.today() + datetime.timedelta(days=1):
                date_string.append("Tomorrow")
            else:
                date_string.append(item["DateString"])

            collect.append(item["Collect"])

        self._next_date = date_string[0]
        self._next_date_2 = date_string[1]
        if "Rubbish" in collect[0]:
            self._is_rubbish = "Yes"
        if "Recycle" in collect[0]:
            self._is_recycle = "Yes"
        if "Rubbish" in collect[1]:
            self._is_rubbish_2 = "Yes"
        if "Recycle" in collect[1]:
            self._is_recycle_2 = "Yes"
