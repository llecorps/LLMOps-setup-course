#!/bin/bash

# Script de démarrage pour le système de cache sémantique Qdrant
# Usage: ./start_cache_system.sh

set -e

echo "🚀 Démarrage du système de cache sémantique LLMOps"
echo "=================================================="

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages colorés
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Vérifier que Docker est installé et en cours d'exécution
check_docker() {
    log_info "Vérification de Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker n'est pas installé. Veuillez installer Docker Desktop."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker n'est pas en cours d'exécution. Veuillez démarrer Docker Desktop."
        exit 1
    fi
    
    log_success "Docker est disponible"
}

# Vérifier que docker-compose est disponible
check_compose() {
    log_info "Vérification de Docker Compose..."
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose n'est pas disponible."
        exit 1
    fi
    
    log_success "Docker Compose est disponible"
}

# Nettoyer les anciens conteneurs si nécessaire
cleanup_old_containers() {
    log_info "Nettoyage des anciens conteneurs..."
    
    # Arrêter les conteneurs existants
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # Supprimer les anciens volumes Redis si ils existent
    docker volume rm llmops-setup-course_redis_data 2>/dev/null || true
    docker volume rm llmops-setup-course_redis_insight_data 2>/dev/null || true
    
    log_success "Nettoyage terminé"
}

# Construire et démarrer les services
start_services() {
    log_info "Construction et démarrage des services..."
    
    # Construire les images
    log_info "Construction des images Docker..."
    docker-compose build --no-cache
    
    # Démarrer les services
    log_info "Démarrage des services..."
    docker-compose up -d
    
    log_success "Services démarrés"
}

# Attendre que les services soient prêts
wait_for_services() {
    log_info "Attente de la disponibilité des services..."
    
    # Fonction pour attendre un service
    wait_for_service() {
        local service_name=$1
        local url=$2
        local max_attempts=30
        local attempt=1
        
        log_info "Attente de $service_name..."
        
        while [ $attempt -le $max_attempts ]; do
            if curl -s "$url" > /dev/null 2>&1; then
                log_success "$service_name est prêt"
                return 0
            fi
            
            echo -n "."
            sleep 2
            ((attempt++))
        done
        
        log_error "$service_name n'est pas disponible après $max_attempts tentatives"
        return 1
    }
    
    # Attendre Qdrant
    wait_for_service "Qdrant" "http://localhost:6333/health"
    
    # Attendre TEI
    wait_for_service "TEI Embeddings" "http://localhost:8080/health"
    
    # Attendre MLflow
    wait_for_service "MLflow" "http://localhost:5001/health"
    
    # Attendre LiteLLM
    wait_for_service "LiteLLM" "http://localhost:8001/health"
    
    # Attendre l'API
    wait_for_service "API" "http://localhost:8000/health"
    
    log_success "Tous les services sont prêts !"
}

# Afficher les informations de connexion
show_connection_info() {
    echo ""
    echo "🎉 Système de cache sémantique démarré avec succès !"
    echo "=================================================="
    echo ""
    echo "📋 Services disponibles :"
    echo "   • API principale      : http://localhost:8000"
    echo "   • Documentation API   : http://localhost:8000/docs"
    echo "   • LiteLLM Proxy      : http://localhost:8001"
    echo "   • MLflow UI          : http://localhost:5001"
    echo "   • Qdrant Web UI      : http://localhost:6334"
    echo "   • TEI Embeddings     : http://localhost:8080"
    echo ""
    echo "🔧 Outils de gestion :"
    echo "   • Logs en temps réel : docker-compose logs -f"
    echo "   • Statistiques cache : curl http://localhost:8000/llm/cache/stats"
    echo "   • Test du système    : python test_cache.py"
    echo ""
    echo "📚 Documentation :"
    echo "   • Architecture       : CACHE_ARCHITECTURE.md"
    echo "   • Tests             : test_cache.py"
    echo ""
    echo "🛑 Pour arrêter :"
    echo "   docker-compose down"
    echo ""
}

# Fonction principale
main() {
    echo ""
    
    # Vérifications préalables
    check_docker
    check_compose
    
    # Nettoyage et démarrage
    cleanup_old_containers
    start_services
    wait_for_services
    
    # Informations finales
    show_connection_info
    
    # Proposer de lancer les tests
    echo -n "Voulez-vous lancer les tests automatiques ? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Lancement des tests..."
        echo ""
        log_warning "N'oubliez pas de mettre à jour le JWT_TOKEN dans test_cache.py"
        echo ""
        python test_cache.py || log_warning "Tests échoués - vérifiez la configuration"
    fi
    
    log_success "Démarrage terminé !"
}

# Gestion des signaux pour un arrêt propre
trap 'log_warning "Arrêt demandé..."; docker-compose down; exit 0' INT TERM

# Exécution du script principal
main "$@"
