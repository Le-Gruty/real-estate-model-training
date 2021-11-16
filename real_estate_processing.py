#!/usr/bin/env python
# coding: utf-8
# Import the packages required to run Spark and connect to S3
import os
os.environ['PYSPARK_SUBMIT_ARGS'] =     "--packages=com.amazonaws:aws-java-sdk-bundle:1.11.714,\
	org.apache.hadoop:hadoop-aws:2.8.5"
from pyspark.sql import SparkSession
import pyspark.sql.functions as f
from dotenv import load_dotenv

# Load .env file credentials for S3
load_dotenv()
accessKey = os.environ.get('accessKey')
secretKey = os.environ.get('secretKey')

# Create a Spark Session and configures S3 credentials
spark = (
	SparkSession.builder.appName("RealEstateDataPicture")
	.config("spark.hadoop.fs.s3a.access.key",accessKey)
	.config("spark.hadoop.fs.s3a.secret.key", secretKey)
	.config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
	.config("spark.hadoop.fs.s3a.path.style.access", "true")
	.config("spark.hadoop.fs.s3a.endpoint", "s3.gra.cloud.ovh.net")
	.getOrCreate()
)

# Read all the pattern-matching CSV files from a S3 bucket (in that case OVHcloud Public Cloud Storage) and 
# create a Spark Dataframe
path = "s3a://transactions-ecoex-raw/files*.csv"
data = spark.read.format('csv').options(header='true', inferSchema='true')   .load(path) 



data_clean = (
# Filter data from transactions that happened outside Paris
	data.filter((data.code_departement == 75) & (data.nature_mutation == 'Vente'))
# Remove unnecessary columns
	.select('id_mutation','date_mutation','valeur_fonciere','adresse_numero','adresse_nom_voie',
	'adresse_code_voie','code_postal','lot1_surface_carrez','lot2_surface_carrez',
	'lot3_surface_carrez','lot4_surface_carrez','lot5_surface_carrez','nombre_lots','type_local',
	'surface_reelle_bati','nombre_pieces_principales','surface_terrain','longitude','latitude')
# Group rows by id_mutation which is a unique transaction identifier. Valeur_fonciere (which is the price)
# is kept only a single time because it is present on all the lines corresponding to a single transaction
	.groupBy('id_mutation').agg(
	f.first('date_mutation').alias('date_mutation'),
	f.first('valeur_fonciere').alias('valeur_fonciere'),
	f.first('adresse_numero').alias('adresse_numero'),
	f.first('adresse_nom_voie').alias('adresse_nom_voie'),
	f.min('adresse_code_voie').alias('adresse_code_voie'),
	f.min('code_postal').alias('code_postal'),
	f.sum('lot1_surface_carrez').alias('lot1_surface_carrez'),
	f.sum('lot2_surface_carrez').alias('lot2_surface_carrez'),
	f.sum('lot3_surface_carrez').alias('lot3_surface_carrez'),
	f.sum('lot4_surface_carrez').alias('lot4_surface_carrez'),
	f.sum('lot5_surface_carrez').alias('lot5_surface_carrez'),
	f.sum('nombre_lots').alias('nombre_lots'),
	f.concat_ws(" , ",f.collect_list(f.col('type_local'))).alias('type_local'),
	f.sum('surface_reelle_bati').alias('surface_reelle_bati'),
	f.sum('nombre_pieces_principales').alias('nombre_pieces_principales'),
	f.sum('surface_terrain').alias('surface_terrain'),
	f.first('longitude').alias('longitude'),
	f.first('latitude').alias('latitude'))
# Fill the NULL values with zeroes in the surface and price columns
	.na.fill(value=0,subset=['valeur_fonciere','lot1_surface_carrez',
	'lot2_surface_carrez','lot3_surface_carrez','lot4_surface_carrez',
	'lot5_surface_carrez','surface_terrain'])
# Sum the surface columns into a new, unique one then delete the initial ones
	.withColumn('surface_carrez',f.col('lot1_surface_carrez')+f.col('lot2_surface_carrez')+
	f.col('lot3_surface_carrez')+f.col('lot4_surface_carrez')+f.col('lot5_surface_carrez'))
	.select('id_mutation','date_mutation','valeur_fonciere','adresse_numero',
	'adresse_nom_voie','adresse_code_voie','code_postal','surface_carrez','nombre_lots',
	'type_local','surface_reelle_bati','nombre_pieces_principales','surface_terrain',
	'longitude','latitude')
# Add a new column to display the price per square meter
	.withColumn('prix_m2',f.col('valeur_fonciere')/f.col('surface_carrez'))
# Filter irrelevant or obviously bad data as well as obvious outliers
	.filter((f.col('surface_carrez')>0)&(f.col('type_local').contains('Appartement'))&
	(f.col('valeur_fonciere')>50000)&(f.col('surface_terrain') == 0)&(f.col('valeur_fonciere')<4000000)&
	(f.col('prix_m2')<40000)&(f.col('prix_m2')>2000))
)

data_clean.describe('valeur_fonciere','prix_m2','code_postal','surface_carrez',\
	'nombre_pieces_principales').show()

# Writes the result as a parquet file to another S3 bucket
pathWrite= "s3a://transactions-ecoex-clean/data_clean.parquet"
data_clean.write.mode("overwrite").parquet(pathWrite)

spark.stop()