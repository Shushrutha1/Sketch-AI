#!/usr/bin/env bash
set -e

echo "========================================================================="
echo "   Initializing AI-Enhanced Collaborative Drawing Game Platform Setup    "
echo "========================================================================="

# Establish virtual isolated execution tracking context configurations
python3 -m venv venv
source venv/bin/activate

echo "Installing verified architectural software package specifications..."
pip install --upgrade pip
pip install -r Backend/requirements.txt

echo "Initializing machine learning structural classifications model training..."
python ML/train_model.py

if [ ! -f .env ]; then
    echo "Creating environment structure instance from standard configuration profile templates..."
    cp .env.example .env
fi

echo "========================================================================="
echo " Execution environment initialized successfully.                          "
echo " Run 'source venv/bin/activate && python Backend/app.py' to launch server."
echo "========================================================================="