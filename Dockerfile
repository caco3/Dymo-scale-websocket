FROM python

RUN mkdir -p /app

COPY Dymo-Waage/app/* /app/

WORKDIR /app

COPY Dymo-Waage/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "bash", "run.sh"]
