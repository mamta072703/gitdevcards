FROM nginx:alpine
# Install envsubst (gettext) for runtime template substitution
RUN apk add --no-cache gettext
WORKDIR /usr/share/nginx/html
COPY index.html /usr/share/nginx/html/index.html.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
