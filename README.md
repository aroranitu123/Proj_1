       SOURCE SYSTEMS
  ┌──────────┬──────────┬──────────┐
  │ Meta &   │   CRM    │  Store   │
  │ Google   │   CSV    │   JSON   │
  │ Ads API  │          │          │
  └────┬─────┴────┬─────┴────┬─────┘
       └──────────┼──────────┘
                  ▼
          EXTRACTION LAYER
       Pagination | Retry | API
                  ▼
          RAW DATA LAYER
       Original data + metadata
                  ▼
        STAGING / CLEANING
     Type conversion | Deduplication
      Standardisation | Validation
                  ▼
           FINAL LAYER
       PostgreSQL Tables
                  ▼
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    Dashboard    ML       AI Agent
                        (Pogee)
