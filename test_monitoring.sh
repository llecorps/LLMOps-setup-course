#!/bin/bash

# Script de test du monitoring LLMOps
echo "🧪 Test du système de monitoring LLMOps..."

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de test
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="$3"
    
    echo -n "Testing $name... "
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✅ OK (HTTP $status)${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED (HTTP $status, expected $expected_status)${NC}"
        return 1
    fi
}

echo ""
echo "📊 1. Test des endpoints de monitoring..."

# Test des endpoints de base
test_endpoint "Health Check" "http://localhost:8000/monitoring/health" "200"
test_endpoint "System Stats" "http://localhost:8000/monitoring/stats" "200"
test_endpoint "Prometheus Metrics" "http://localhost:8000/monitoring/metrics" "200"

echo ""
echo "🔥 2. Test des services principaux..."

# Test des services
test_endpoint "FastAPI" "http://localhost:8000/" "200"
test_endpoint "LiteLLM" "http://localhost:8001/health" "200"
test_endpoint "MLflow" "http://localhost:5001/" "200"
test_endpoint "Qdrant" "http://localhost:6333/health" "200"
test_endpoint "Prometheus" "http://localhost:9090/" "200"
test_endpoint "Grafana" "http://localhost:3000/" "200"

echo ""
echo "🚀 3. Test de requêtes LLM pour générer des métriques..."

# Générer quelques requêtes LLM pour créer des métriques
for i in {1..3}; do
    echo -n "Requête LLM #$i... "
    response=$(curl -s -X POST http://localhost:8001/chat/completions \
        -H "Content-Type: application/json" \
        -d '{
            "model": "groq-kimi-primary",
            "messages": [
                {"role": "user", "content": "Test monitoring request #'$i'"}
            ],
            "max_tokens": 20
        }')
    
    if echo "$response" | grep -q "choices"; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "Response: $response"
    fi
    sleep 1
done

echo ""
echo "📈 4. Vérification des métriques après les requêtes..."

# Attendre un peu pour que les métriques se mettent à jour
sleep 3

echo "Stats du système:"
curl -s http://localhost:8000/monitoring/stats | jq . 2>/dev/null || curl -s http://localhost:8000/monitoring/stats

echo ""
echo "Métriques Prometheus (échantillon):"
curl -s http://localhost:8000/monitoring/metrics | grep -E "llmops_|python_info" | head -5

echo ""
echo -e "${YELLOW}📋 Résumé des accès:${NC}"
echo "  • API FastAPI:     http://localhost:8000"
echo "  • LiteLLM:         http://localhost:8001"
echo "  • MLflow:          http://localhost:5001"
echo "  • Qdrant:          http://localhost:6333"
echo "  • Prometheus:      http://localhost:9090"
echo "  • Grafana:         http://localhost:3000 (admin/admin)"
echo ""
echo "  • Monitoring API:  http://localhost:8000/monitoring/health"
echo "  • Métriques:       http://localhost:8000/monitoring/metrics"
echo "  • Stats système:   http://localhost:8000/monitoring/stats"

echo ""
echo -e "${GREEN}🎉 Test du monitoring terminé !${NC}"
echo ""
echo -e "${YELLOW}💡 Prochaines étapes:${NC}"
echo "  1. Ouvrir Grafana: http://localhost:3000 (admin/admin)"
echo "  2. Importer le dashboard LiteLLM depuis /monitoring/grafana/dashboards/"
echo "  3. Configurer des alertes si nécessaire"
echo "  4. Surveiller les métriques en temps réel"
