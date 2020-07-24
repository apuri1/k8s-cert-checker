import logging
import time
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest
from threading import Thread

logger = logging.getLogger(("gunicorn.error"))
logger.setLevel(logging.INFO)


class CustomCollector(object):
    def __init__(self, k8sdata):
        self.k8sdata = k8sdata

    def collect(self):

        try:
            for key, value in self.k8sdata.items():
                g = GaugeMetricFamily(
                    "certification_expiration_days",
                    "certificate expiration",
                    labels=["namespace", "secret", "certificate"],
                )
                g.add_metric([key[0], key[1], key[2]], value)
                yield g
        except TypeError as e:
            logger.error(e)


class FetchMetrics(Thread):
    def __init__(self, mutex_thr, mutex_endpoint, k8sdata, metrics):
        Thread.__init__(self)
        self.k8sdata = k8sdata
        self.metrics = metrics
        self.mutex_thr = mutex_thr
        self.mutex_endpoint = mutex_endpoint

    def run(self):
        while True:
            logger.debug("fetchmetrics_thr waiting on k8s")
            self.mutex_thr.acquire()
            logger.debug("fetchmetrics_thr has acquired lock")

            registry = CustomCollector(self.k8sdata)

            collected_metric = generate_latest(registry)

            self.mutex_thr.notify()
            logger.debug("fetchmetrics_thr has notified and releasing lock")
            self.mutex_thr.release()

            logger.debug("fetchmetrics_thr waiting on endpoint")
            self.mutex_endpoint.acquire()
            logger.debug("fetchmetrics_thr has acquired lock")

            self.metrics.extend(collected_metric)
            self.mutex_endpoint.notify()
            logger.debug("fetchmetrics_thr has completed populating data")
            self.mutex_endpoint.release()

            time.sleep(600)