export $(grep -v '^#' ../../.env.example | xargs)
dispatch database revision --autogenerate
