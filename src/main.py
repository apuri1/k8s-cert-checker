import logging
from flask import Flask, Response
from queryk8s import QueryK8s
from custommetrics import FetchMetrics
from threading import Condition


app = Flask(__name__)

logger = logging.getLogger(("gunicorn.error"))
logger.setLevel(logging.INFO)

mutex_thr = Condition()
mutex_endpoint = Condition()

k8sdata = {}
metrics = bytearray()


def initialise_threads():

    logger.debug("Initialising threads")

    queryk8s_thr = QueryK8s(mutex_thr, k8sdata)
    queryk8s_thr.start()

    fetchmetrics_thr = FetchMetrics(mutex_thr, mutex_endpoint, k8sdata, metrics)
    fetchmetrics_thr.start()

    logger.debug("Threads started")


initialise_threads()


@app.route("/metrics")
def handle_prometheus():
    mutex_endpoint.acquire()
    logger.debug("handle_prometheus has acquired lock")
    msg = metrics.decode("utf-8")
    mutex_endpoint.notify()
    logger.debug("handle_prometheus has completed, ready to send")
    mutex_endpoint.release()
    return Response(msg)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8000)