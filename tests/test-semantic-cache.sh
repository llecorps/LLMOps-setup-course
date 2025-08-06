#!/bin/bash

echo "🔍 Test spécifique du cache sémantique"
echo "====================================="

# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "secret123"}' \
    | jq -r '.access_token')

echo "🔐 Token obtenu: ${TOKEN:0:20}..."

# Test 1: Premier prompt unique
echo ""
echo "🔍 Test 1: Premier prompt complètement nouveau"
RESPONSE1=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "How can I protect my REST API from attacks?", "max_tokens": 80}')

echo "Réponse 1: $(echo $RESPONSE1 | jq -r '.response' | head -c 80)..."

# Test 2: Prompt sémantiquement très similaire mais formulé différemment
echo ""
echo "🔍 Test 2: Prompt sémantiquement similaire (différentes mots)"
sleep 3  # Attendre que le cache soit indexé

RESPONSE2=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "What methods exist to secure a REST API against malicious requests?", "max_tokens": 80}')

echo "Réponse 2: $(echo $RESPONSE2 | jq -r '.response' | head -c 80)..."

# Test 3: Prompt complètement différent (pas de cache attendu)
echo ""
echo "🔍 Test 3: Prompt complètement différent (pas de cache attendu)"
RESPONSE3=$(curl -s -X POST http://localhost:8000/llm/generate \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"model": "groq-kimi-primary", "prompt": "Explain quantum computing concepts", "max_tokens": 80}')

echo "Réponse 3: $(echo $RESPONSE3 | jq -r '.response' | head -c 80)..."

echo ""
echo "🔍 Vérification des logs pour cache sémantique..."
