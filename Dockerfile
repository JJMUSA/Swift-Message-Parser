FROM python:3.11-windowsservercore-1809

ENV HOME=/home/app
RUN mkdir $HOME
WORKDIR $HOME
COPY BICDIR2018_V1_FULL_20231229.txt \
     db_init.py \
     email_template.html\
     mail.py \
     PdfReader.py \
     requirements.txt \
     template.html \
     .env $HOME
COPY static/ $HOME/static/

RUN apt-get update
RUN apt-get install -y libgobject-2.0-0 libpango-1.0-0 libcairo2 libpangoft2-1.0-0 libharfbuzz-subset0
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python","PdfReader.py"]