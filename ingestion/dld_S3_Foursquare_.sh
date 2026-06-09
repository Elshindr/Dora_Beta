#!/bin/bash

#aws s3 sync s3://fsq-os-places-us-east-1/release/dt=2025-05-09/categories/parquet/ ./categories-data/ --no-sign-request
#aws s3 sync s3://fsq-os-places-us-east-1/release/dt=2025-05-09/places/parquet/ ./places-data/ --no-sign-request

aws s3 sync s3://fsq-os-places-us-east-1/release/dt=2025-09-09/deltas/parquet/--no-sign-request ./delta/ --no-sign-request