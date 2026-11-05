#!/usr/bin/env bash
# Root-owned systemd launcher. Browser and publisher run WITHOUT root privileges.
set -euo pipefail
umask 027
: "${INCT_IMAGE:?Set the immutable image ID in runner.env}"
: "${INCT_PUBLISH_MODE:=none}" # none | stage | activate (explicit operator gate)
case "$INCT_PUBLISH_MODE" in none|stage|activate) ;; *) echo 'Invalid publish mode' >&2; exit 2;; esac
exec 9>/run/lock/scriptlattes-inct.lock
flock -n 9 || { echo 'Another INCT run is active' >&2; exit 1; }
uid=$(id -u scriptlattes)
gid=$(id -g scriptlattes)
# Clean up only the container created by THIS invocation. A failed overlapping
# service must never stop a manual refresh that already owns the lock.
cidfile="/run/scriptlattes-inct-$$.cid"
cleanup() {
  if [ -f "$cidfile" ]; then
    IFS= read -r container_id < "$cidfile" || :
    if [[ "${container_id:-}" =~ ^[a-f0-9]{64}$ ]]; then
      docker rm -f "$container_id" >/dev/null 2>&1 || :
    fi
    rm -f "$cidfile"
  fi
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
# Updates/queries require no SSH credential inside the container.
docker run --rm --init --name scriptlattes-inct --cidfile "$cidfile" \
  --user "$uid:$gid" --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --pids-limit 256 \
  --memory 3g --cpus 2 --shm-size 256m --ulimit nofile=4096:4096 \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m,mode=1777 \
  -v /etc/scriptlattes:/config:ro \
  -v /srv/scriptlattes:/data:rw \
  "$INCT_IMAGE" --config /config/inct.config --state-dir /data \
  --seed-cache /data/seed-cache "$@"
# Dry runs and explicit offline runs never auto-publish via this launcher.
for arg in "$@"; do
  case "$arg" in --check-only|--offline) exit 0;; esac
done
if [ "$INCT_PUBLISH_MODE" != none ]; then
  activate=()
  if [ "$INCT_PUBLISH_MODE" = activate ]; then activate=(--activate); fi
  runuser -u scriptlattes -- /usr/bin/python3 /opt/scriptlattes/scripts/inct_publish.py \
    --state-dir /srv/scriptlattes --host inct-vision \
    --ssh-config /var/lib/scriptlattes/.ssh/config "${activate[@]}"
fi
