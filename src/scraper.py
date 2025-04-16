"""
Lanceur principal pour l'application Google Maps Scraper avec interface graphique.
"""
import logging
# Importer la fonction main de la GUI
from .gui import main as launch_gui

# Configurer le logging de base ici ou dans chaque module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Lancement de l'interface graphique Google Maps Scraper...")
    launch_gui()
    logger.info("Interface graphique fermée.")
