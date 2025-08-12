#!/bin/bash

# Script de démarrage du monitoring LiteLLM
# Ce script démarre tous les services avec monitoring automatique

echo "🚀 Démarrage du système LLMOps avec monitoring..."

# Vérifier que Docker est en cours d'exécution
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker n'est pas en cours d'exécution. Veuillez démarrer Docker."
    exit 1
fi

# Arrêter les services existants s'ils sont en cours d'exécution
echo "🛑 Arrêt des services existants..."
docker-compose down

# Construire et démarrer tous les services
echo "🔨 Construction et démarrage des services..."
docker-compose up -d --build

# Attendre que les services soient prêts
echo "⏳ Attente du démarrage des services..."
sleep 30

# Vérifier l'état des services
echo "🔍 Vérification de l'état des services..."

services=("api:8000" "litellm:4000" "mlflow:5000" "qdrant:6333" "tei-embeddings:80" "prometheus:9090" "grafana:3000")
for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -f -s "http://localhost:$port/health" > /dev/null 2>&1 || curl -f -s "http://localhost:$port" > /dev/null 2>&1; then
        echo "✅ $name (port $port) - OK"
    else
        echo "⚠️  $name (port $port) - En cours de démarrage..."
    fi
done

echo ""
echo "🎉 Système LLMOps avec monitoring démarré !"
echo ""
echo "📊 Accès aux services :"
echo "  • API FastAPI:     http://localhost:8000"
echo "  • LiteLLM Proxy:   http://localhost:8001"
echo "  • MLflow:          http://localhost:5001"
echo "  • Qdrant:          http://localhost:6333"
echo "  • Prometheus:      http://localhost:9090"
echo "  • Grafana:         http://localhost:3000 (admin/admin)"
echo ""
echo "📈 Métriques LiteLLM: http://localhost:8001/metrics"
echo ""
echo "🔧 Pour tester le système :"
echo "  make test-cache-system"
echo ""
echo "📋 Pour voir les logs :"
echo "  docker-compose logs -f [service_name]"
