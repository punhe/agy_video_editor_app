#!/bin/bash
# Double-click launcher for macOS Finder. Uses the same setup as run_app.sh.
cd "$(dirname "$0")"
bash ./run_app.sh "$@"
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo
    read -n 1 -s -r -p "Có lỗi xảy ra. Bấm phím bất kỳ để đóng..."
fi
exit $STATUS
