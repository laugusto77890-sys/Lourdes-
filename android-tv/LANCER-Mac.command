#!/bin/sh
cd "$(dirname "$0")"
python3 outils/tv_allegement.py tout
echo
read -p "Appuyez sur Entrée pour fermer…" x
