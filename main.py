import streamlit as st
import pandas as pd 
from operator import itemgetter
import boto3
import json
import io
import csv

st.title ("SageMaker Labelling Tracker")

choice = st.sidebar.selectbox("What would you like to do?", options = ["Analyse Completed Projects", "Track an Ongoing Project"])

if choice == "Analyse Completed Projects":
    options = ["Project View", "Labeller View", "Overall View"]

    selected_view = st.sidebar.selectbox("Select a View", options)
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket = 'labelling-sagemaker-test', Key = 'metrics.csv')
    lines = obj['Body'].read().decode("utf-8")
    buf = io.StringIO(lines)
    reader = csv.DictReader(buf)
    rows = list(reader) 
    data = pd.DataFrame (rows)
    data['annotation_time_taken'] = data['annotation_time_taken'].astype(float)
    data['review_time_taken'] = data['review_time_taken'].astype(float)
    class_index = {}
    i = 0
    for label in list(data["class_name"].unique()):
        if len (label) > 0:
            class_index [label] = i
            i += 1

    def get_class_name (index):
        for key, val in class_index.items():
            if val == index:
                return key

    def get_correct_annotations (df):
        annotation_count = len (df)
        correct_annotation_count = df['response'].value_counts()['Approve']
        correct_unique_annotation_count = len(df.loc[(df['response'] == 'Approve') & (len (df['class_name']) > 0)])
        st.write ("*Number of Correct Annotations:*")
        st.success (f"{correct_annotation_count} out of {annotation_count}")
        st.write ("*Accuracy %:*")
        st.success (f"{round (correct_annotation_count/annotation_count * 100, 2)}%")
        st.write ("*Number of correctly annotated screen-classes:*")
        st.success (f"{correct_unique_annotation_count}")

    def get_correct_annotations_min_element (df):
        classes_correct = {}
        classes_count = {}
        for i in range (len (df)):
            class_name = df.loc [i, "class_name"]
            response = df.loc [i, "response"]
            if len (class_name) > 0:
                if class_name not in classes_count:
                    classes_correct [class_name] = 0
                    classes_count [class_name] = 0
                if response == "Approve":
                    classes_correct [class_name] += 1
                classes_count [class_name] += 1
        st.write ("*Number of correct annotations for elements with least number of annotations:*")
        min_classes = dict(sorted(classes_count.items(), key = itemgetter(1))[:5])
        for min_class in min_classes.keys():
            min_annotated_class_count = classes_count [min_class]
            min_annotated_class_correct = classes_correct [min_class]
            st.write (f"- {min_annotated_class_correct} out of {min_annotated_class_count} for {min_class}")

    def get_worker_accuracy (df):
        worker_correct = {}
        worker_count = {}
        worker_accuracy = {}
        for i in range (len (df)):
            worker = df.loc [i, "annotation_worker_id"]
            review = df.loc [i, "response"]
            if worker not in worker_count:
                worker_count [worker] = 0
                worker_correct [worker] = 0
            if review == "Approve":
                worker_correct [worker] += 1
            worker_count [worker] += 1
        for w in worker_count.keys():
            worker_accuracy [w] = round (worker_correct [w] / worker_count [w] * 100, 2)
        for key, val in worker_accuracy.items():
            st.write (f"{key} : {val}%")

    def get_worker_accuracy_by_class (df):
        worker_correct_classes = {}
        worker_count_classes = {}
        num_classes = len (class_index) 
        for i in range (len (df)):
            worker = df.loc [i, "annotation_worker_id"]
            review = df.loc [i, "response"]
            label = df.loc [i, "class_name"]
            if worker not in worker_count_classes:
                worker_count_classes [worker] = [0] * num_classes
                worker_correct_classes [worker] = [0] * num_classes
            if len (label) > 0:
                if review == "Approve": 
                    worker_correct_classes [worker][class_index [label]]+= 1
                worker_count_classes [worker][class_index [label]] += 1
        worker_accuracy_classes = {}
        for w in worker_count_classes:
            correct = worker_correct_classes [w]
            count = worker_count_classes [w]
            acc = []
            for i in range (len (count)):
                if count [i] != 0:
                    acc.append (correct[i]/count[i] * 100)
                else:
                    acc.append (0)
            worker_accuracy_classes [w] = acc
        accuracy_df = pd.DataFrame (worker_accuracy_classes)
        accuracy_df["class"] = [get_class_name (i) for i in accuracy_df.index]
        accuracy_df = accuracy_df.set_index ("class")
        return accuracy_df

    if selected_view == "Project View":
        project_options = data["project"].unique()
        selected_project = st.sidebar.selectbox("Select a Project", project_options)
        project = data[data["project"] == selected_project].reset_index()
        st.subheader (f"Project: {selected_project}")
        get_correct_annotations (project)
        approved = project [project["response"] == "Approve"]
        st.write ("*Breakdown of Correctly Annotated Screen-Classes by Class:*")
        st.table (approved["class_name"].value_counts())
        get_correct_annotations_min_element (project)

        df = project.drop_duplicates("source-ref")
        st.write ("*Annotation Time Taken within Project:*")
        st.table (df.groupby ("annotation_worker_id").sum()["annotation_time_taken"])
        st.write ("*Review Time Taken within Project:*")
        st.table (df.groupby ("review_worker_id").sum()["review_time_taken"])
        st.write ("*Worker Accuracy within Project:*")
        get_worker_accuracy (project)
        st.write ("*Worker Accuracy by Class within Project:*")
        st.table (get_worker_accuracy_by_class (project))

    elif selected_view == "Labeller View":
        st.write ("*Number of Annotations per Labeller:*")
        approved = data.loc[data['response'] == 'Approve']
        num_correct = approved.groupby ("annotation_worker_id").count()["source-ref"]
        num_total = data.groupby ("annotation_worker_id").count()["source-ref"]
        num_total = pd.DataFrame(num_total).rename (columns= {"source-ref": "Total Annotations"})
        num_correct = pd.DataFrame(num_correct).rename (columns= {"source-ref": "Correct Annotations"})
        labeller_df = pd.merge (num_total, num_correct, left_index=True, right_index=True)
        labeller_df ["Accuracy"] = round (labeller_df [labeller_df.columns[1]]/ labeller_df [labeller_df.columns[0]] * 100, 2)
        st.table (labeller_df)

        st.write ("*Accuracy per Class by Labeller:*")
        class_grouped = data.groupby(["annotation_worker_id", "class_name"])
        workers = []
        accuracy = {}
        for group in class_grouped:
            worker = group [0][0]
            if worker not in workers:
                workers.append (worker)
            class_name = group [0][1]
            annotations = group [1]
            num_annotations = len (annotations)
            correct_annotations = len (annotations[annotations["response"]== "Approve"])
            if class_name not in accuracy:
                accuracy [class_name] = []
            accuracy [class_name].append (round (correct_annotations/num_annotations * 100, 2))
        accuracy_df = pd.DataFrame (accuracy)
        accuracy_df ["workers"] = workers
        accuracy_df = accuracy_df.set_index ("workers")
        st.table (accuracy_df)

        st.write ("*Overall Time Spent:*")
        df = data.drop_duplicates (["source-ref", "project"])
        label_times = {}
        grouped = df.groupby("annotation_worker_id")
        for group in grouped:
            worker = group [0]
            annotations = group [1]
            time_spent = sum (annotations["annotation_time_taken"])
            label_times [worker] = time_spent

        review_times = {}
        grouped = df.groupby("review_worker_id")
        for group in grouped:
            worker = group [0]
            annotations = group [1]
            time_spent = sum (annotations["review_time_taken"])
            review_times [worker] = time_spent

        times_df = pd.DataFrame()
        times_df ["worker"] = label_times.keys()
        times_df ["labelling_time"] = label_times.values ()
        times_df ["reviewing_time"] = review_times.values ()
        st.table (times_df)

    else:
        get_correct_annotations (data)
        approved = data[data["response"] == "Approve"]
        st.write ("*Breakdown of Correctly Annotated Screen-Classes by Class:*")
        st.table (approved["class_name"].value_counts())
        get_correct_annotations_min_element (data)

        df = data.drop_duplicates(["source-ref", "project"])
        st.write ("*Overall Annotation Time Taken:*")
        st.table (df.groupby ("annotation_worker_id").sum()["annotation_time_taken"])
        st.write ("*Overall Review Time Taken:*")
        st.table (df.groupby ("review_worker_id").sum()["review_time_taken"])
        st.write ("*Overall Worker Accuracy:*")
        get_worker_accuracy (data)
        st.write ("*Overall Worker Accuracy by Class:*")
        st.table (get_worker_accuracy_by_class (data))

else:
    project = st.sidebar.selectbox ("Select a Project", options = ["cards"])
    if project == "cards":
        bucket = 'labelling-sagemaker-test'
        input_path = 'cards_labelling_job/cards.jsonl'
        review_path = 'cards_labelling_job/output/card-label-job-sample-v1-chain-review'
        annotation_path = 'cards_labelling_job/output/card-label-job-sample-v1'

        s3 = boto3.resource('s3', aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"], aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"])
        key = f'{input_path}'

        obj = s3.Object(bucket, key)
        file_content = obj.get()['Body'].read().decode('utf-8')

        json_content = [json.loads(line) for line in file_content.split('\n') if line]

        df = pd.DataFrame(json_content)

        num_images = len (df)
        client = boto3.client('cognito-idp', aws_access_key_id = st.secrets["AWS_ACCESS_KEY_ID"], aws_secret_access_key = st.secrets["AWS_SECRET_ACCESS_KEY"])
        user_pool_id = st.secrets["user_pool_id"]

        users = client.list_users(UserPoolId=user_pool_id)

        user_details = {}
        for user in users ["Users"]:
            sub = user ["Attributes"][0]["Value"]
            email = user ["Attributes"][2]["Value"]
            user_details [sub] = email
            
        workers = []
        times = []
        labels = []

        for i in range (num_images):
            s3_resource = boto3.resource('s3') 
            objects = s3.Bucket(name='labelling-sagemaker-test').objects.all()
            for object in objects:
                if object.key.startswith (f'{annotation_path}/annotations/worker-response/iteration-1/{i}/'):
                    key = object.key
            obj = s3.Object(bucket, key)
            file_content = obj.get()['Body'].read().decode('utf-8')
            json_content = [json.loads(line) for line in file_content.split('\n') if line]
            df = pd.DataFrame(json_content)
            times.append (df["answers"][0][0]["timeSpentInSeconds"])
            workers.append (user_details [df["answers"][0][0]["workerMetadata"]["identityData"]["sub"]])
            labels.append ([x["label"] for x in df["answers"][0][0]["answerContent"]["boundingBox"]["boundingBoxes"]])

        labelled_images = pd.DataFrame({"labels": labels, "workers": workers, "times": times})
        st.subheader ("Labelling")

        # Workers currently working on Project
        st.write (f"Labellers working on Project: {set (workers)}")

        # Completion of project
        st.write (f"*Status:* {len (times)} images labelled out of {num_images} so far.")

        annotations = 0
        class_count = {}
        for l in labels:
            for x in l:
                annotations += 1
                if x not in class_count:
                    class_count [x] = 1
                else:
                    class_count [x] += 1
                
        st.success (f"*Number of unique screen-classes:* {annotations}")
        st.write ("*Breakdown of unique screen-classes by class:*")

        for key, val in class_count.items():
            st.write (f"- {key}: {val}")

        reviewers = []
        review_times = []
        reviews = []


        for i in range (num_images - 5):
            s3_resource = boto3.resource('s3') 
            objects = s3.Bucket(name='labelling-sagemaker-test').objects.all()
            for object in objects:
                if object.key.startswith (f'{review_path}/annotations/worker-response/iteration-1/{i}/'):
                    key = object.key
            obj = s3.Object(bucket, key)
            file_content = obj.get()['Body'].read().decode('utf-8')
            json_content = [json.loads(line) for line in file_content.split('\n') if line]
            df = pd.DataFrame(json_content)
            review_times.append (df["answers"][0][0]["timeSpentInSeconds"])
            reviewers.append (user_details [df["answers"][0][0]["workerMetadata"]["identityData"]["sub"]])
            reviews.append (df["answers"][0][0]["answerContent"]["annotatedResult"]["label"])

        reviewed_images = pd.DataFrame ({"reviews": reviews, "reviewers": reviewers, "review_times": review_times})
        
        st.subheader ("Reviewing")

        # Workers currently working on Project
        st.write (f"Reviewers working on Project: {set (reviewers)}")

        # Completion of project
        st.write (f"*Status:* {len (review_times)} images reviewed out of {num_images} so far.")

        # Images left to be reviewed
        st.write ("*Screen-Classes Labelled but Unreviewed:*")
        last_reviewed = len (review_times)
        classes_unreviewed = (labelled_images[last_reviewed:])["labels"]
        unreviewed = []
        for image in classes_unreviewed:
            for label in image:
                if len (label) > 0:
                    unreviewed.append (label)
        unreviewed_df = pd.Series(unreviewed).value_counts().reset_index().rename(columns = {0: "count"})
        for i in range (len (unreviewed_df)):
            label = unreviewed_df.loc [i, "index"]
            count = unreviewed_df.loc [i, "count"]
            st.write(f"- {label}: {count}")
