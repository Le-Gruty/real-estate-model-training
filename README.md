# Real-estate model training: How to use machine learning to make a good deal when buying a flat!

## Preparing your setup

### Setting up your environment

For all the manipulations described in the second phase of this article, I use a Virtual Machine deployed in OVHcloud's Public Cloud, in Graveline's datacenter. It is a `d2-4` flavor with 4GB of RAM, 2 vCores and 50 GB of local storage running Debian 10. During this tutorial, I run a few UNIX commands but you should easily be able to adapt them to whatever OS you use if needed. All the CLI tools specific to OVHcloud's products are available on multiple OSs.

You will also need an OVHcloud NIC (user account) as well as a Public Cloud Project created for this account with a high-enough quota (you might have to use CPU instead of GPU in the final step if your quota is not high enough). To create a Public Cloud project, you can follow [these steps](https://docs.ovh.com/gb/en/public-cloud/create_a_public_cloud_project/).

### Installing and configuring your tools

Here is a list of the CLI tools and other that we will use during this tutorial and why - note that everything done here can be done on the manager (OVHcloud's web UI), in which case you don't need to install any tool and can do everything on your browser:

* `wget` to retrieve the data from a public data website.
* `gunzip` to unzip it.
* `aws` CLI, that we will use to interact with OVHcloud's Public Cloud Storage, a product allowing you to manipulate object storage buckets either through the Swift or the S3 API. Alternatively, you could use the `Swift` CLI. You will find how to configure your `aws` CLI [here](https://docs.ovh.com/gb/en/public-cloud/getting_started_with_the_swift_S3_API/).
* `ovh-spark-submit` CLI to launch OVHcloud data processing (Spark-as-a-Service) jobs. You will find the instructions to install and configure the CLI [here](https://docs.ovh.com/gb/en/data-processing/submit-cli/).
* `ovhai` CLI to launch OVHcloud AI notebook or AI training jobs. You will find out how to install and configure this CLI [here](https://docs.ovh.com/gb/en/ai-training/install-client/).
* All the code files necessary can be found on this repository.
* The raw data we use for this tutorial can be found [here](https://files.data.gouv.fr/geo-dvf/) (This tutorial uses only the full file for every year: the per-department/city file didn't exist at the time of writing).

### Creating your object storage buckets

In this tutorial, we will use several object storage buckets. Since we will use the S3 API, we will call them S3 bucket, but as mentioned above, if you use OVHcloud standard Public Cloud Storage, you could also use the Swift API. However, you are restricted to only the S3 API if you use our new [high-performance object storage](https://labs.ovh.com/high-perf-object-storage) offer, currently in Beta.

For this tutorial, we are going to create and use the following S3 buckets:

* `transactions-ecoex-raw` to store the raw data before it is processed
* `transactions-ecoex-processing` to store the Spark code and environment files used to process the raw data
* `transactions-ecoex-clean`to store the data once it has been cleaned 
* `transactions-ecoex-model`to store the weights of the trained model once it has been trained

To create these buckets, use the following commands after having configured your aws CLI as explained above:

```
aws s3 mb s3://transactions-ecoex-raw
aws s3 mb s3://transactions-ecoex-processing
aws s3 mb s3://transactions-ecoex-clean
aws s3 mb s3://transactions-ecoex-model
```
Now that you have your environment set up and your S3 buckets ready, we can begin the tutorial!

## Tutorial

### Ingesting the Data

First, let us download the data files directly on Etalab's website and unzip them:

```
wget -r -l2 -P data -np "https://files.data.gouv.fr/geo-dvf/latest/csv/" -A "*full.csv.gz" --reject-regex="/communes/|/departements/"
cd data
for FILE in `find files.data.gouv.fr -name "*.csv.gz"`
do
  	NEWFILE=`echo $FILE | tr '/' '-'`
  	mv $FILE $NEWFILE
done
rm -rf files.data.gouv.fr/*
rm -r files.data.gouv.fr
gunzip *.csv.gz
```
You should now have the following files in your directory, each one corresponding to the French real estate transaction of a specific year:

```console
debian@d2-4-gra5:~/data$ ls
files.data.gouv.fr-geo-dvf-latest-csv-2016-full.csv  
files.data.gouv.fr-geo-dvf-latest-csv-2019-full.csv
files.data.gouv.fr-geo-dvf-latest-csv-2017-full.csv  
files.data.gouv.fr-geo-dvf-latest-csv-2020-full.csv
files.data.gouv.fr-geo-dvf-latest-csv-2018-full.csv
```
Now, use the S3 CLI to push these files in the relevant S3 bucket:

```
find * -type f -name "*.csv" -exec aws s3 cp {} s3://transactions-ecoex-raw/{} \;
```
You should now have those 5 files in your S3 bucket:

```console
debian@d2-4-gra5:~/data$ aws s3 ls transactions-ecoex-raw
2021-09-21 17:43:32  511804467 files.data.gouv.fr-geo-dvf-latest-csv-2016-full.csv
2021-09-21 17:43:54  590281357 files.data.gouv.fr-geo-dvf-latest-csv-2017-full.csv
2021-09-21 17:44:14  580600597 files.data.gouv.fr-geo-dvf-latest-csv-2018-full.csv
2021-09-21 17:44:36  614788794 files.data.gouv.fr-geo-dvf-latest-csv-2019-full.csv
2021-09-21 17:44:52  426715300 files.data.gouv.fr-geo-dvf-latest-csv-2020-full.csv
```
What we just did with a small VM was ***ingesting*** data into a S3 bucket. In real-life usecases with more data, we would probably use dedicated tools to ingest the data. However, in our example with just a few GB of data coming from a public website, this does the trick. 

### Processing the data

Now that you have your raw data in place to be processed, you just have to upload the code necessary to run your data processing job. OVHcloud's data processing product allows you to run Spark code written either in Java, Scala or Python. In our case, we use Pyspark on Python. Your code should consist in 3 files:

* A .py file containing your code. In our case, this file is `real_estate_processing.py`
* A `environment.yml` file containing your dependencies.
* If you don't wish to put your S3 credentials in your .py file, a separate `.env` file containing them. You will need to use a library like `python-dotenv` to handle that.

Once you have your code files, go to the folder containing them and push them on the appropriate S3 bucket:

```
cd real-estate-model-training
aws s3 cp real_estate_processing.py s3://transactions-ecoex-processing/processing.py
aws s3 cp environment.yml s3://transactions-ecoex-processing/environment.yml
aws s3 cp .env s3://transactions-ecoex-processing/.env
```
Your bucket should now look like that:

```console
debian@d2-4-gra5:~/real-estate-model-training$ aws s3 ls transactions-ecoex-processing
2021-10-04 10:14:52         94 .env
2021-10-04 10:14:09         99 environment.yml
2021-10-04 10:20:08       4425 processing.py
```

You are now ready to launch your data processing job. The following command will allow you to launch this job on 10 executors, each with 4 vCores and 15 GB of RAM.

```
ovh-spark-submit \
	--projectid $OS_PROJECT_ID \
	--jobname transactions-ecoex-processing \
	--class org.apache.spark.examples.SparkPi \
	--driver-cores 4 \
	--driver-memory 15G \
	--executor-cores 4 \
	--executor-memory 15G \
	--num-executors 10 \
	swift://transactions-ecoex-processing/processing.py 1000
```
Note that the data processing product uses the Swift API to retrieve the code files. This is totally transparent to the user, and the fact that we used the S3 CLI to create the bucket has absolutely no impact. When the job is over, you should see the following in your `transactions-ecoex-clean` bucket:

```console
debian@d2-4-gra5:~$ aws s3 ls transactions-ecoex-clean
     						PRE data_clean.parquet/
debian@d2-4-gra5:~$ aws s3 ls transactions-ecoex-clean/data_clean.parquet/
2021-10-04 16:35:48          0 _SUCCESS
2021-10-04 16:27:13      50769 part-00000-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
2021-10-04 16:27:16      52253 part-00001-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
2021-10-04 16:27:18      51412 part-00002-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
2021-10-04 16:27:21      46962 part-00003-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
2021-10-04 16:27:23      49130 part-00004-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
2021-10-04 16:27:26      50046 part-00005-ac3acfc2-c5b3-430e-91b4-7f5e50b537a6-c000.snappy.parquet
.......
```

Your data is now clean and ready to be used to train a model!

### Training the model

To train the model, you are going to use OVHcloud AI notebook to deploy a notebook. With the following command, you will:

* Deploy a notebook running a Jupyterlab, ...
* ... pre-configured to run on a VM with 4 GPUs, ...
* ... with several important libraries such as Tensorflow or Pytorch installed, ...
* ... with your S3 bucket `transactions-ecoex-clean` synchronized on a high-performance storage cluster that is mounted on `/workspace/data`in your notebook, ...
* ... and ready to write the model when it has been trained on the `/workspace/model` path that will be synchronized with your `transactions-ecoex-model` when the job is over.


```
ovhai notebook run one-for-all jupyterlab \
	--name transactions-ecoex-training \
	--framework-version v98-ovh.beta.1 \
	--flavor ai1-1-gpu \
	--gpu 1 \
	--volume transactions-ecoex-clean@GRA/:/workspace/data:RO \
	--volume transactions-ecoex-model@GRA/:/workspace/model:RW

```

Once this is done, just get the URL of your notebook with the following command and connect to it with your browser:

```console
debian@d2-4-gra5:~$ ovhai notebook list
ID                                   STATE   AGE FRAMEWORK   VERSION          EDITOR     URL
525bcb3e-d57b-4111-91ff-4a8759061f75 RUNNING 20m one-for-all v98-ovh.beta.1   jupyterlab https://525bcb3e-d57b-4111-91ff-4a8759061f75.notebook.gra.training.ai.cloud.ovh.net
```

You can now import the `real-estate-training.ipynb` file to the notebook. If you don't want to import it from the computer you use to access the notebook (for example if like me you use a VM to work and have cloned the git repo on this VM and not on your computer), you can push the `.ipynb` file to your `transactions-ecoex-clean` or `transactions-ecoex-model` bucket and re-synchronize the bucket to your notebook while it runs by using the `ovhai notebook pull-data` command. You will then find the notebook file in the corresponding directory.

Once you have imported the notebook file to your notebook instance, just open it and follow the directives. When you have finished running the notebook, you should have two separate models saved in a folder on your notebook. Don't forget to stop your notebook to stop being charged and synchronize back the trained models to your S3 bucket!


