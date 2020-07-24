# python threading with k8s access

A k8s deployment running in the tools namespace.
Checks expiration dates of all *.pem and *.crt files in each secret in all namespaces
Exposes metrics for prometheus to scrape.