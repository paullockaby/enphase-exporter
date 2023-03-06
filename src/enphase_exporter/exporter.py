import importlib.metadata
import json
import logging
import time
from time import perf_counter as time_now

import prometheus_client
import requests
import tenacity
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

logger = logging.getLogger(__name__)


def get_version(package_name: str = __name__) -> str:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


class APIClient:
    def __init__(self: "APIClient", api_url: str) -> None:
        self.api_url = api_url
        self.session = requests.session()
        self.session.headers.update({"User-Agent": ""})

    @tenacity.retry(
        stop=(tenacity.stop_after_delay(30)),
        wait=tenacity.wait_random(min=1, max=2),
        before_sleep=tenacity.before_sleep_log(logger, logging.ERROR),
        reraise=True,
    )
    def call(self: "APIClient", path: str) -> dict:
        api_url = self.api_url.rstrip("/")
        path = path.lstrip("/")
        result = self.session.get(f"{api_url}/{path}")
        result.raise_for_status()

        try:
            return result.json()
        except json.JSONDecodeError:
            logger.error("received invalid data from API:")
            logger.error(result.content)
            raise


class CustomCollector:
    def __init__(self: "CustomCollector", api_url: str) -> None:
        self.client = APIClient(api_url)

    def collect(self: "CustomCollector") -> None:
        timer = time_now()
        data = {
            "production": self.client.call("/production.json"),
            "inverters": self.client.call("/api/v1/production/inverters"),
        }
        logger.info(
            "successfully polled the enphase envoy device in {:.4f} seconds".format(
                time_now() - timer,
            ),
        )

        metrics = {
            "apprnt_pwr": GaugeMetricFamily(
                "solar_apprnt_pwr",
                "Apparent power",
                labels=["meter"],
            ),
            "pwr_factor": GaugeMetricFamily(
                "solar_pwr_factor",
                "Power factor",
                labels=["meter"],
            ),
            "react_pwr": GaugeMetricFamily(
                "solar_react_pwr",
                "Reactive power",
                labels=["meter"],
            ),
            "vah_today": GaugeMetricFamily(
                "solar_vah_today",
                "Volt-amp-hours today",
                labels=["meter"],
            ),
            "vah_lifetime": CounterMetricFamily(
                "solar_vah_lifetime",
                "Volt-amp-hours lifetime",
                labels=["meter"],
            ),
            "varh_lag_today": GaugeMetricFamily(
                "solar_varh_lag_today",
                "Volt-amp-reactive-hours lag today",
                labels=["meter"],
            ),
            "varh_lag_lifetime": CounterMetricFamily(
                "solar_varh_lag_lifetime",
                "Volt-amp-reactive-hours lag lifetime",
                labels=["meter"],
            ),
            "varh_lead_today": GaugeMetricFamily(
                "solar_varh_lead_today",
                "Volt-amp-reactive-hours lead today",
                labels=["meter"],
            ),
            "varh_lead_lifetime": CounterMetricFamily(
                "solar_varh_lead_lifetime",
                "Volt-amp-reactive-hours lead lifetime",
                labels=["meter"],
            ),
            "w_now": GaugeMetricFamily(
                "solar_w_now",
                "Current watts",
                labels=["meter"],
            ),
            "wh_today": GaugeMetricFamily(
                "solar_wh_today",
                "Watt-hours today",
                labels=["meter"],
            ),
            "wh_last7days": GaugeMetricFamily(
                "solar_wh_last7days",
                "Watt-hours last seven days",
                labels=["meter"],
            ),
            "wh_lifetime": CounterMetricFamily(
                "solar_wh_lifetime",
                "Watt-hours lifetime",
                labels=["meter"],
            ),
            "last_report_watts": GaugeMetricFamily(
                "solar_inverter_last_report_watts",
                "Watts reported by solar panel",
                labels=["panel"],
            ),
            "last_report_time": GaugeMetricFamily(
                "solar_inverter_last_report_time",
                "Time of last report",
                labels=["panel"],
            ),
        }

        for inverter in data["inverters"]:
            metrics["last_report_watts"].add_metric(
                [inverter["serialNumber"]],
                inverter["lastReportWatts"],
            )
            metrics["last_report_time"].add_metric(
                [inverter["serialNumber"]],
                inverter["lastReportDate"],
            )

        for datum in data["production"]["production"]:
            if datum.get("measurementType", "") == "production":
                metrics["apprnt_pwr"].add_metric(["production"], datum["apprntPwr"])
                metrics["pwr_factor"].add_metric(["production"], datum["pwrFactor"])
                metrics["react_pwr"].add_metric(["production"], datum["reactPwr"])
                metrics["vah_today"].add_metric(["production"], datum["vahToday"])
                metrics["vah_lifetime"].add_metric(["production"], datum["vahLifetime"])
                metrics["varh_lag_today"].add_metric(
                    ["production"],
                    datum["varhLagToday"],
                )
                metrics["varh_lag_lifetime"].add_metric(
                    ["production"],
                    datum["varhLagLifetime"],
                )
                metrics["varh_lead_today"].add_metric(
                    ["production"],
                    datum["varhLeadToday"],
                )
                metrics["varh_lead_lifetime"].add_metric(
                    ["production"],
                    datum["varhLeadLifetime"],
                )
                metrics["w_now"].add_metric(["production"], datum["wNow"])
                metrics["wh_today"].add_metric(["production"], datum["whToday"])
                metrics["wh_last7days"].add_metric(
                    ["production"],
                    datum["whLastSevenDays"],
                )
                metrics["wh_lifetime"].add_metric(["production"], datum["whLifetime"])

        for datum in data["production"]["consumption"]:
            if datum.get("measurementType", "") == "total-consumption":
                metrics["apprnt_pwr"].add_metric(["consumption"], datum["apprntPwr"])
                metrics["pwr_factor"].add_metric(["consumption"], datum["pwrFactor"])
                metrics["react_pwr"].add_metric(["consumption"], datum["reactPwr"])
                metrics["vah_today"].add_metric(["consumption"], datum["vahToday"])
                metrics["vah_lifetime"].add_metric(
                    ["consumption"],
                    datum["vahLifetime"],
                )
                metrics["varh_lag_today"].add_metric(
                    ["consumption"],
                    datum["varhLagToday"],
                )
                metrics["varh_lag_lifetime"].add_metric(
                    ["consumption"],
                    datum["varhLagLifetime"],
                )
                metrics["varh_lead_today"].add_metric(
                    ["consumption"],
                    datum["varhLeadToday"],
                )
                metrics["varh_lead_lifetime"].add_metric(
                    ["consumption"],
                    datum["varhLeadLifetime"],
                )
                metrics["w_now"].add_metric(["consumption"], datum["wNow"])
                metrics["wh_today"].add_metric(["consumption"], datum["whToday"])
                metrics["wh_last7days"].add_metric(
                    ["consumption"],
                    datum["whLastSevenDays"],
                )
                metrics["wh_lifetime"].add_metric(["consumption"], datum["whLifetime"])

        yield from metrics.values()


def run(
    port: int,
    api_url: str,
) -> None:
    logger.info(f"starting exporter on port {port} connecting to {api_url}")
    prometheus_client.start_http_server(port)

    # disable metrics that we do not care about
    prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
    prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)

    # enable our custom metric collector
    prometheus_client.REGISTRY.register(CustomCollector(api_url))

    while True:
        time.sleep(10)
