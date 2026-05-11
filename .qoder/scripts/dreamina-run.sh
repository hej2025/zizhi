#\!/bin/bash
exec /snap/core22/2411/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 \
  --library-path /snap/core22/2411/usr/lib/x86_64-linux-gnu:/snap/core22/2411/lib/x86_64-linux-gnu \
  /home/hej/.local/bin/dreamina "$@"
