#!/bin/sh

rm -f *.pem *.crt *.key

openssl genrsa -aes256 -passout pass:1234 -out server.pass.key 4096
openssl rsa -passin pass:1234 -in server.pass.key -out server.key
openssl req -new -key server.key -out server.csr

openssl x509 -req -sha256 -days 365 -in server.csr -signkey server.key -out server.crt