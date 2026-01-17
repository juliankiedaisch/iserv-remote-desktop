ARG BASE_TAG="latest"
ARG BASE_IMAGE="kasm-core-ubuntu"
FROM teacherki/$BASE_IMAGE:$BASE_TAG
USER root

ENV HOME /home/kasm-default-profile
ENV STARTUPDIR /dockerstartup
ENV INST_SCRIPTS $STARTUPDIR/install
ENV DONT_PROMPT_WSL_INSTALL "No_Prompt_please"
WORKDIR $HOME

######### Customize Container Here ###########

# Set Password
RUN echo "kasm-user:password" | chpasswd
RUN usermod -a -G sudo kasm-user

# Install Filius
#COPY ./src/filius_2.9.4_all.deb $INST_SCRIPTS/filius_2.9.4_all.deb
RUN apt-get update
#RUN apt-get update && apt-get -y install default-jre
#RUN dpkg -i $INST_SCRIPTS/filius_2.9.4_all.deb
RUN apt-get -y install filius

COPY ./src/filius_custom_startup.sh $STARTUPDIR/custom_startup.sh
RUN chmod +x $STARTUPDIR/custom_startup.sh
RUN chmod 755 $STARTUPDIR/custom_startup.sh

# Update the desktop environment to be optimized for a single application
RUN cp $HOME/.config/xfce4/xfconf/single-application-xfce-perchannel-xml/* $HOME/.config/xfce4/xfconf/xfce-perchannel-xml/
RUN cp /usr/share/backgrounds/bg_kasm.png /usr/share/backgrounds/bg_default.png
RUN apt-get remove -y xfce4-panel

######### End Customizations ###########

RUN chown 1000:0 $HOME

ENV HOME /home/kasm-user
WORKDIR $HOME
RUN mkdir -p $HOME && chown -R 1000:0 $HOME

USER 1000
