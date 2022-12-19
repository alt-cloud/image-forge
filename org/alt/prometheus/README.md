# Prometheus image

Command for run:
```
docker run -d --name="prometheus" -p 9090:9090 -v promdata:/var/lib/prometheus IMAGENAME
```

*If you want to be able to view services on localhost, instead of -p, specify the flag:
```
--network="host"
```
Prometheus will see all the services running on your local hosting, without this it will not be able to access your ports


To upload your own configuration, create prometheus.yml, you can use example from:
```
https://raw.githubusercontent.com/prometheus/prometheus/main/documentation/examples/prometheus.yml
```
Then, while the container is running, enter its command:
```
docker cp $PWD/prometheus.yml prometheus:/etc/prometheus/prometheus.yml

docker restart prometheus
```
