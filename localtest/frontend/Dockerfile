FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY style.css  /usr/share/nginx/html/style.css
COPY app.js     /usr/share/nginx/html/app.js
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY cmux.png   /usr/share/nginx/html/cmux.png
COPY aim.webp   /usr/share/nginx/html/aim.webp

EXPOSE 80
