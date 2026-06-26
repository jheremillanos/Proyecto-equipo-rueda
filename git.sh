#!/bin/bash
# Ejecutar EN LA RPI, dentro de /home/rpiuser/A_final
set -e

cd /home/rpiuser/A_final

# 1. .gitignore
cat > .gitignore << 'IG'
__pycache__/
*.pyc
registro_estudiantes.json
*.log
.venv/
IG

# 2. Init + commit + version
git init
git add .
git commit -m "Proyecto Sistema Educativo Inteligente - version inicial"
git branch -M main
git tag v1.0

# 3. Ramas
git branch develop
git branch rpi
git branch pico

# 4. Remoto + push (todas las ramas y tags)
git remote add origin https://github.com/jheremillanos/Examen-Final-1t-equipo-rueda.git
git push -u origin main
git push origin develop rpi pico
git push origin --tags

echo ""
echo "LISTO. Ramas subidas: main, develop, rpi, pico  |  Tag: v1.0"