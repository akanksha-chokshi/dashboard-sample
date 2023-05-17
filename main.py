import streamlit as st
import pandas as pd 
from operator import itemgetter

st.title ("SageMaker Labelling Tracker")

options = ["Project View", "Labeller View", "Overall View"]

selected_view = st.sidebar.selectbox("Select a View", options)
data = pd.read_csv ("metrics.csv")
data ["date"] = data ["date"].apply (lambda x: pd.to_datetime(x))

class_index = {}
i = 0
for label in list(data["class_name"].unique()):
    if isinstance(label, str):
        class_index [label] = i
        i += 1

def get_class_name (index):
    for key, val in class_index.items():
        if val == index:
            return key

def get_correct_annotations (df):
    annotation_count = len (df)
    correct_annotation_count = df['response'].value_counts()['Approve']
    correct_unique_annotation_count = len(df.loc[(df['response'] == 'Approve') & (~df['class_name'].isna())])
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
        if isinstance(class_name, str):
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
        if isinstance (label, str):
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








