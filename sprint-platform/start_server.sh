#!/bin/bash
cd /home/dhruba/Documents/exp_money/daily_learning_freelance/sprint-platform
exec .venv/bin/python -c "
from app import create_app
app = create_app()
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.run(host='0.0.0.0', port=5000, debug=False)
"
