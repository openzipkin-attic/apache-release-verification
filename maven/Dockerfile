FROM openjdk:8-jdk-stretch

RUN apt-get install -y wget git gnupg subversion maven

# Script will use:
#     wget -r -np -R "index.html" -nH --cut-dirs=3 https://dist.apache.org/repos/dist/dev/incubator/zipkin/brave-karaf/0.1.2/
# Parameterize the directory
# Detect other values from structure, ie: isIncubator=[ -d incubator ], projectName=zipkin, moduleName=brave-karaf, version...
