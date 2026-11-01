# -*- coding: utf-8 -*-
"""命令行入口: python -m app.factors.feature_pipeline"""
from app.services.feature_engineering_service import run_feature_engineering


def main():
    result = run_feature_engineering(
        stock_codes="",
        start_date="2023-01-01",
        end_date="2025-12-31",
    )
    print(f"\ndone rows={result['rows']} kept={len(result['kept_features'])} high_corr={result['high_corr_count']}")


if __name__ == "__main__":
    main()
