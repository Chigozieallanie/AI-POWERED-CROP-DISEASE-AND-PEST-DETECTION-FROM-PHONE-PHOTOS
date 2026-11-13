#!/usr/bin/env bash
# Resumable download of two KaraAgro fall armyworm archives (CC0), verified by MD5.
cd "$(dirname "$0")/data" || exit 1
fetch() { id=$1; f=$2; want=$3
  [ -d "faw/${f%.rar}" ] && [ -n "$(ls -A "faw/${f%.rar}")" ] && { echo "already $f"; return; }
  for try in $(seq 1 20); do
    echo "try $try $f at $(stat -c %s "$f" 2>/dev/null)"
    curl -fL -sS -C - -o "$f" "https://dataverse.harvard.edu/api/access/datafile/$id" && break
    sleep 10
  done
  sum=$(md5sum "$f" | cut -d" " -f1); echo "md5 $f $sum"
  if [ "$sum" = "$want" ]; then mkdir -p "faw/${f%.rar}"; unrar x -o+ -inul "$f" "faw/${f%.rar}/" && rm "$f"; echo "unrar exit $?"
  else echo "CHECKSUM FAIL $f"; fi
}
fetch 6418158 faw_05.rar 9a6c3fb0c278a8d2246b08147e88acab
fetch 6418191 faw_07.rar f960c613ec1085b04dc8af1d70a9898e
echo "jpgs $(find faw -iname '*.jpg' | wc -l)"; echo FINISHED
