ARG BASE_TAG="latest"
ARG BASE_IMAGE="kasm-core-ubuntu"
FROM teacherki/$BASE_IMAGE:$BASE_TAG
USER root

ENV HOME /home/kasm-default-profile
ENV STARTUPDIR /dockerstartup
ENV INST_SCRIPTS $STARTUPDIR/install
ENV LANG de_DE.UTF-8
ENV LANGUAGE de_DE:de
ENV LC_ALL de_DE.UTF-8
WORKDIR $HOME

######### Customize Container Here ###########

# Set Password
RUN echo "kasm-user:password" | chpasswd
RUN usermod -a -G sudo kasm-user

RUN apt-get update && apt-get -y install python3-tk python3-pip python3-pygame

# Install Google Chrome
COPY ./src/install_chrome.sh $INST_SCRIPTS/chrome/
RUN bash $INST_SCRIPTS/chrome/install_chrome.sh  && rm -rf $INST_SCRIPTS/chrome/
# Install VSCode
COPY ./src/install_vs_code.sh $INST_SCRIPTS/vs_code/
RUN bash $INST_SCRIPTS/vs_code/install_vs_code.sh  && rm -rf $INST_SCRIPTS/vs_code/
#Install Filius
RUN apt-get update && apt-get -y install filius
#Install Firefox
COPY ./src $INST_SCRIPTS/firefox/
RUN bash $INST_SCRIPTS/firefox/install_firefox.sh  && rm -rf $INST_SCRIPTS/firefox/
#Install Gimp
RUN apt-get update && apt-get -y install gimp
#Install LibreOffice
COPY ./src $INST_SCRIPTS/libre_office/
RUN bash $INST_SCRIPTS/libre_office/install_libre_office.sh  && rm -rf $INST_SCRIPTS/libre_office/
######### End Customizations ###########

RUN chown 1000:0 $HOME
RUN $STARTUPDIR/set_user_permission.sh $HOME

ENV HOME /home/kasm-user
WORKDIR $HOME
RUN mkdir -p $HOME && chown -R 1000:0 $HOME

USER 1000