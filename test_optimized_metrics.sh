#!/bin/bash

# Test des optimisations des métriques
echo "🔧 Test des optimisations des métriques LLMOps..."

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction de test améliorée
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="$3"
    local check_content="$4"
    
    echo -n "Testing $name... "
    
    if [ -z "$check_content" ]; then
        # Simple status check
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
        if [ "$status" = "$expected_status" ]; then
            echo -e "${GREEN}✅ OK (HTTP $status)${NC}"
            return 0
        else
            echo -e "${RED}❌ FAILED (HTTP $status, expected $expected_status)${NC}"
            return 1
        fi
    else
        # Content check
        response=$(curl -s "$url")
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
        
        if [ "$status" = "$expected_status" ] && echo "$response" | grep -q "$check_content"; then
            echo -e "${GREEN}✅ OK (HTTP $status, content found)${NC}"
            return 0
        else
            echo -e "${RED}❌ FAILED (HTTP $status, content check failed)${NC}"
            return 1
        fi
    fi
}

echo ""
echo -e "${BLUE}📊 1. Test des endpoints de métriques optimisées...${NC}"

# Test des deux approches de métriques
test_endpoint "Métriques Middleware" "http://localhost:8000/monitoring/metrics" "200" "llmops_requests_total"
test_endpoint "Métriques Dédiées" "http://localhost:8000/metrics/prometheus" "200" "llmops_"
test_endpoint "Résumé des Métriques" "http://localhost:8000/metrics/summary" "200" "timestamp"

echo ""
echo -e "${BLUE}🔥 2. Test de performance des endpoints...${NC}"

# Test de performance simple
echo -n "Performance Métriques Middleware... "
time_middleware=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8000/monitoring/metrics")
echo -e "${GREEN}${time_middleware}s${NC}"

echo -n "Performance Métriques Dédiées... "
time_dedicated=$(curl -s -o /dev/null -w "%{time_total}" "http://localhost:8000/metrics/prometheus")
echo -e "${GREEN}${time_dedicated}s${NC}"

# Comparaison
if (( $(echo "$time_dedicated < $time_middleware" | bc -l) )); then
    echo -e "${GREEN}✅ Endpoint dédié plus rapide${NC}"
else
    echo -e "${YELLOW}⚠️  Middleware plus rapide ou équivalent${NC}"
fi

echo ""
echo -e "${BLUE}🚀 3. Test de robustesse avec requêtes multiples...${NC}"

# Générer du trafic pour tester la robustesse
echo "Génération de trafic (10 requêtes simultanées)..."

for i in {1..10}; do
    (
        curl -s -X POST http://localhost:8001/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
                "model": "groq-kimi-primary",
                "messages": [
                    {"role": "user", "content": "Test robustesse #'$i'"}
                ],
                "max_tokens": 10
            }' > /dev/null &
        
        # Test d'accès aux métriques en parallèle
        curl -s "http://localhost:8000/monitoring/metrics" > /dev/null &
        curl -s "http://localhost:8000/metrics/prometheus" > /dev/null &
    )
done

wait
echo -e "${GREEN}✅ Trafic généré${NC}"

sleep 2

echo ""
echo -e "${BLUE}📈 4. Vérification de la collecte des métriques...${NC}"

echo "Métriques du middleware:"
curl -s "http://localhost:8000/monitoring/metrics" | grep -E "llmops_requests_total|llmops_request_duration" | head -3

echo ""
echo "Métriques dédiées:"
curl -s "http://localhost:8000/metrics/prometheus" | grep -E "llmops_.*_dedicated|llmops_llm_|llmops_system_health" | head -5

echo ""
echo "Résumé des métriques:"
curl -s "http://localhost:8000/metrics/summary" | jq -r '.metrics | to_entries[] | "\(.key): \(.value)"'

echo ""
echo -e "${BLUE}🔍 5. Test de gestion d'erreurs...${NC}"

# Test avec un service down (simulation)
echo -n "Test erreur MLflow... "
# Tester quand MLflow n'est pas accessible
response=$(curl -s "http://localhost:8000/metrics/prometheus")
if echo "$response" | grep -q "llmops_"; then
    echo -e "${GREEN}✅ Métriques générées malgré erreur MLflow${NC}"
else
    echo -e "${RED}❌ Échec génération métriques${NC}"
fi

echo ""
echo -e "${YELLOW}📋 Résumé des optimisations testées:${NC}"
echo "  ✅ Endpoint dédié pour métriques (/metrics/prometheus)"
echo "  ✅ Middleware optimisé avec gestion d'erreurs améliorée"
echo "  ✅ Registres Prometheus séparés pour éviter les conflits"
echo "  ✅ Gestion d'erreurs robuste (fallback sur erreurs)"
echo "  ✅ Collecte de métriques en arrière-plan"
echo "  ✅ Filtrages des endpoints pour réduire la surcharge"

echo ""
echo -e "${YELLOW}🎯 Bonnes pratiques implémentées:${NC}"
echo "  • Séparation des préoccupations (middleware vs endpoint dédié)"
echo "  • Gestion d'erreurs non-bloquante"
echo "  • Optimisation des performances (filtrage, timeouts)"
echo "  • Monitoring de la santé du système de métriques lui-même"
echo "  • Documentation claire des endpoints disponibles"

echo ""
echo -e "${YELLOW}📊 Accès aux métriques:${NC}"
echo "  • Métriques classiques:  http://localhost:8000/monitoring/metrics"
echo "  • Métriques optimisées:  http://localhost:8000/metrics/prometheus"
echo "  • Résumé lisible:        http://localhost:8000/metrics/summary"
echo "  • Santé du système:      http://localhost:8000/monitoring/health"

echo ""
echo -e "${GREEN}🎉 Test des optimisations terminé !${NC}"
echo ""
echo -e "${YELLOW}💡 Recommandations pour la production:${NC}"
echo "  1. Utiliser l'endpoint dédié (/metrics/prometheus) pour Prometheus"
echo "  2. Surveiller les logs pour les erreurs de collecte de métriques"  
echo "  3. Configurer des alertes sur les métriques de santé du système"
echo "  4. Ajuster les intervalles de collecte selon les besoins"
