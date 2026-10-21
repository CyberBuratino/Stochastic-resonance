#!/bin/sh
# Run the portable build when available; otherwise run the editable source.
cd -- "$(dirname -- "$0")" || exit 1
if [ -x "./StochasticResonance" ]; then
    exec ./StochasticResonance
fi
if [ -x "./dist/StochasticResonance/StochasticResonance" ]; then
    exec ./dist/StochasticResonance/StochasticResonance
fi
exec python3 main.py
