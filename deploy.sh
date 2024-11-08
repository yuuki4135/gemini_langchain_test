#!/bin/bash

sam build

# 環境変数の値を確認
echo "GOOGLE_API_KEY: $GOOGLE_API_KEY"

sam deploy --parameter-overrides \
  GppgleApiKey="$GOOGLE_API_KEY" \
