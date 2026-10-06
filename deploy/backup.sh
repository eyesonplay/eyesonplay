#!/bin/sh
# Database backups: a pg_dump (custom format) every BACKUP_INTERVAL_S seconds
# (default daily) into /backups, deleting dumps older than BACKUP_KEEP_DAYS.
# Restore: pg_restore --clean --if-exists -d "$PGDATABASE" eyesonplay-<stamp>.dump
set -u
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL_S="${BACKUP_INTERVAL_S:-86400}"

while true; do
	stamp=$(date -u +%Y%m%dT%H%M%SZ)
	target="/backups/eyesonplay-$stamp.dump"
	if pg_dump --format=custom --file="$target.partial"; then
		mv "$target.partial" "$target"
		echo "backup written: $target"
	else
		rm -f "$target.partial"
		echo "backup FAILED at $stamp" >&2
	fi
	find /backups -name 'eyesonplay-*.dump' -mtime +"$KEEP_DAYS" -delete
	sleep "$INTERVAL_S"
done
