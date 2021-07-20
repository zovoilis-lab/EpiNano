FROM ppc64le/ubuntu

ENV DEBIAN_FRONTEND=noninteractiv
#Dockerfile Mantainer
LABEL mantainer="m.stuartedwards@uleth.ca"
USER root
#Update the centos software with yum package-manager
#RUN yum update -y && yum clean all
RUN apt update &&  apt upgrade -y

#Install git, wget and nano package
#RUN yum -y install git wget nano python2 && yum clean all
RUN apt install -y git wget nano samtools build-essential zlib1g-dev libbz2-dev liblzma-dev python-dev python3-pip python3-venv libffi7 systemd minimap2 libblas3 liblapack3 liblapack-dev libblas-dev gfortran libatlas-base-dev libtiff5-dev libjpeg8-dev libopenjp2-7-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk libharfbuzz-dev libfribidi-dev libxcb1-dev libhdf5-dev
#gtf_splicesites

#RUN ln -s /usr/bin/python2 /usr/bin/python

#RUN wget https://bootstrap.pypa.io/pip/2.7/get-pip.py \
#    && python get-pip.py \
#    && python -m pip install pysam pandas

# Install IBM Advance Toolchain
#Run wget https://public.dhe.ibm.com/software/server/POWER/Linux/toolchain/at/ubuntu/dists/focal/6976a827.gpg.key \
#    &&  apt-key add 6976a827.gpg.key
#Run echo 'deb https://public.dhe.ibm.com/software/server/POWER/Linux/toolchain/at/ubuntu bionic at13.0' >> /etc/apt/sources.list \
#    && apt update
#Run apt-get -y install advance-toolchain-at13.0-runtime advance-toolchain-at13.0-devel advance-toolchain-at13.0-perf advance-toolchain-at13.0-mcore-libs
#WORKDIR /dependencies/IBM
#RUN wget https://public.dhe.ibm.com/software/server/POWER/Linux/toolchain/at/ubuntu/dists/xenial/at12.0/binary-ppc64el/advance-toolchain-at12.0-runtime_12.0-5_ppc64el.deb \
#    && dpkg -i advance-toolchain-at12.0-runtime_12.0-5_ppc64el.deb

ENV PATH=/opt/at12.0/bin:$PATH

# Install Nanopolish
RUN --mount=type=ssh git clone --recursive https://github.com/zovoilis-lab/nanopolish.git /dependencies/nanopolish

WORKDIR /dependencies/nanopolish/minimap2

# Execute another git pull on minimap2
RUN git pull origin master 

WORKDIR /dependencies/nanopolish/
RUN pip install -r scripts/requirements.txt \
    && make

ADD * /home/epiNano/

WORKDIR /home/epiNano/

# Install EpiNano dependencies
RUN chmod +x INSTALL.sh \
    && ./INSTALL.sh

