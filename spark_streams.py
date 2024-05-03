import logging
from cassandra.cluster import Cluster
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType



def create_keyspace(session):
    session.execute("""
            CREATE KEYSPACE IF NOT EXISTS from_spark
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};
        """)

    print("Keyspace created successfully!")

def create_table(session):
    session.execute("""
    CREATE TABLE IF NOT EXISTS from_spark.created_users (
        id UUID PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        gender TEXT,
        address TEXT,
        post_code TEXT,
        email TEXT,
        username TEXT,
        registered_date TEXT,
        phone TEXT,
        picture TEXT);
    """)

    print("Table created successfully!")

###  Batch ###
# def insert_data(session, **kwargs):
#     print("inserting data...")
#
#     user_id = kwargs.get('id')
#     first_name = kwargs.get('first_name')
#     last_name = kwargs.get('last_name')
#     gender = kwargs.get('gender')
#     address = kwargs.get('address')
#     postcode = kwargs.get('post_code')
#     email = kwargs.get('email')
#     username = kwargs.get('username')
#     dob = kwargs.get('dob')
#     registered_date = kwargs.get('registered_date')
#     phone = kwargs.get('phone')
#     picture = kwargs.get('picture')
#
#     try:
#         session.execute("""
#             INSERT INTO spark_streams.created_users(id, first_name, last_name, gender, address,
#                 post_code, email, username, dob, registered_date, phone, picture)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#         """, (user_id, first_name, last_name, gender, address,
#               postcode, email, username, dob, registered_date, phone, picture))
#         logging.info(f"Data inserted for {user_id}, {first_name}, {last_name}")
#
#     except Exception as e:
#         logging.error(f'Data couldnt be inserted due to: {e}')

def create_spark_connection():
    s_conn = None

    try:
        s_conn = (SparkSession.builder
                    .appName('SparkDataStreaming')
                    .master("local")
                    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.4.1,"
                                                   "org.apache.spark:spark-streaming-kafka-0-10_2.12:3.4.1,"
                                                   "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,"
                                                   "org.apache.spark:spark-streaming_2.12:3.4.1,"
                                                   "org.apache.kafka:kafka-clients:3.7.0,"
                                                   "org.apache.kafka:kafka_2.12:3.7.0,"
                                                   "org.apache.hive:hive-jdbc:3.1.3,"
                                                   "org.apache.hive:hive-service:3.1.3,"
                                                   "org.apache.hive:hive-exec:3.1.3,"
                                                   "org.apache.commons:commons-text:1.10.0,"                                                                                                                                                                                                                                         "org.apache.commons:commons-text:1.10.0,"
                                                   "org.apache.commons:commons-lang3:3.12.0,"
                                                   "commons-logging:commons-logging:1.2")
                    .config('spark.cassandra.connection.host', 'localhost')
                    .getOrCreate())

        s_conn.sparkContext.setLogLevel("ERROR")
        logging.info("Spark connection created successfully!")
        print("Spark connection created successfully!")
    except Exception as e:
        logging.error(f"Spark connection error due to exception: {e}")
        print("Spark connection created Unsuccessfully!")
    return s_conn

def connect_to_kafka(spark_connection):
    try:
        spark_dataframe = (spark_connection.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", "localhost:29092")
            .option("subscribe", "user_created")
            .option('failOnDataLoss', 'false')
            .load())
        logging.info("Spark DF created successfully")
        print("Spark DF created successfully!")
        return spark_dataframe
    except Exception as e:
        logging.warning(f"Spark DF couldnt be created because: {e}")
        print("Spark DF created Unsuccessfully!")
        return None

def create_selection_df_from_kafka(input_spark_df):
    schema = StructType([
        StructField("id", StringType(), False),
        StructField("first_name", StringType(), False),
        StructField("last_name", StringType(), False),
        StructField("gender", StringType(), False),
        StructField("address", StringType(), False),
        StructField("post_code", StringType(), False),
        StructField("email", StringType(), False),
        StructField("username", StringType(), False),
        StructField("registered_date", StringType(), False),
        StructField("phone", StringType(), False),
        StructField("picture", StringType(), False)
    ])

    sel = input_spark_df.selectExpr("CAST(value AS STRING)") \
                .select(from_json(col('value'), schema).alias('data')).select("data.*")
    print(sel)

    return sel

def create_cassandra_connection():
    try:
        cluster = Cluster(['localhost'])
        cassandra_session = cluster.connect()
        return cassandra_session
    except Exception as e:
        logging.error(f"Cassandra connection error due to exception: {e}")
        return None



if __name__ == "__main__":
    spark_conn = create_spark_connection()

    if spark_conn is not None:
        spark_df = connect_to_kafka(spark_conn)
        selected_df = create_selection_df_from_kafka(spark_df)
        session = create_cassandra_connection()
        if session is not None:
            create_keyspace(session)
            create_table(session)

            logging.info("Stream started!")
            streaming_query = (selected_df.writeStream
                    .format("org.apache.spark.sql.cassandra")
                    .option('checkpointLocation', '/tmp/checkpoint')
                    .option('keyspace', 'from_spark')
                    .option('table', 'created_users')
                    .start())

            streaming_query.awaitTermination()