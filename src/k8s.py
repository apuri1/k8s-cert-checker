from kubernetes import client, config
from kubernetes.client.rest import ApiException

import OpenSSL
import base64
import logging
import time
from datetime import datetime
from threading import Thread


logger = logging.getLogger(("gunicorn.error"))
logger.setLevel(logging.INFO)


class QueryK8s(Thread):
    def __init__(self, mutex_thr, k8sdata):
        Thread.__init__(self)
        self.k8sdata = k8sdata
        self.today = ""
        self.namespace_list = []
        self.v1 = ""
        self.mutex_thr = mutex_thr

    def run(self):
        while True:
            logger.debug("queryk8s_thr waiting")
            self.mutex_thr.acquire()
            logger.debug("queryk8s_thr has acquired lock")

            if self.get_all_namespaces() < 0:
                logger.error("Could not fetch namespaces")
                self.mutex_thr.notify()
                logger.debug("queryk8s_thr has notified and releasing lock")
                self.mutex_thr.release()
                time.sleep(600)
                continue

            # Clear the dict here, ready to populate
            self.k8sdata.clear()

            if self.get_secrets() < 0:
                logger.error("Could not fetch secrets")
                self.mutex_thr.notify()
                logger.debug("queryk8s_thr has notified and releasing lock")
                self.mutex_thr.release()
                time.sleep(600)
                continue

            self.mutex_thr.notify()
            logger.debug("queryk8s_thr notified and releasing lock")
            self.mutex_thr.release()
            time.sleep(600)

    def get_all_namespaces(self):

        self.today = datetime.today()
        self.namespace_list.clear()

        try:
            # config.load_kube_config()
            config.load_incluster_config()
        except Exception as e:
            logger.error("Exception loading config to access k8s")
            logger.error(e)
            return -1

        self.v1 = client.CoreV1Api()

        try:
            api_response = self.v1.list_namespace()
            logger.debug(api_response)
            for i in api_response.items:
                logger.debug("%s" % (i.metadata.name))
                self.namespace_list.append(i.metadata.name)

        except ApiException as e:
            logger.error("Exception when calling CoreV1Api->list_namespace: %s\n" % e)
            return -1

        return 0

    def get_secrets(self):

        for namespace in self.namespace_list:

            logger.debug("-->processing %s" % namespace)

            try:
                # returns V1SecretList
                secrets = self.v1.list_namespaced_secret(namespace=namespace, watch=False)
            except ApiException as e:
                logger.error("Exception when calling CoreV1Api->list_namespaced_secret: %s\n" % e)
                return -1                

            # from V1SecretList, access V1Secret 'items,
            # and then access the data dict
            for secret in secrets.items:

                # from V1SecretList, access V1Secret ,
                # retrieves all secrets for a namespace
                for key in secret.data.keys():

                    if ".pem" in key.lower() or ".crt" in key.lower():
                        logger.debug(
                            "Processing secret %s/%s, cert %s"
                            % (namespace, secret.metadata.name, key)
                        )

                        # logger.debug("data %s " % secret.data.get(key))

                        self.evaluate(
                            namespace, secret.metadata.name, key, secret.data.get(key)
                        )
        return 0

    def evaluate(self, namespace, secret, certname, cert):

        logger.debug("Evaluting %s, %s, %s" % (namespace, secret, certname))

        try:
            cert_decoded = base64.b64decode(cert)
        except base64.binascii.Error as e:
            logger.error(e)
            logger.error(
                "base64 decode error %s/%s %s, skip" % (namespace, secret, certname)
            )
            return -1

        try:
            x509 = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, cert_decoded
            )

            date_time = x509.get_notAfter().decode("ascii")
        except OpenSSL.crypto.Error as e:
            logger.error(e)
            logger.error("OpenSSL error %s/%s %s, skip" % (namespace, secret, certname))
            return -1

        try:
            date_time = datetime.strptime(date_time, "%Y%m%d%H%M%SZ")

            logger.debug(date_time)

            if(self.today>date_time):
                # Set to arbitrary value 1 so keep alerting
                days_left = 1
                logger.info(f"Cert {namespace}/{secret}/{certname} already expired, set to {days_left} day")
            else:
                days_left = abs((self.today - date_time).days)
                logger.debug(f"Days remaining before expiration: {days_left}\n")

            key = (namespace, secret, certname)
            logger.debug(key)
            self.k8sdata[key] = days_left

        except ValueError as e:
            logger.error(f" {e} ")
            logger.error(f" -> datetime processing error for {certname}")
            return -1

        return 0
        