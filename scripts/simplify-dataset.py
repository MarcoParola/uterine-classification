import argparse
import json
import pandas as pd
import os
import shutil


parser = argparse.ArgumentParser()

parser.add_argument("--folder", type=str, required=True)
parser.add_argument("--config", type=str, default="default")
parser.add_argument("--dry", action="store_true")


args = parser.parse_args()

dataset_file = os.path.join(args.folder, "gyn1.json")

dest_dataset_file = os.path.join(args.folder, "dataset.json")

dataset = json.load(open(dataset_file, "r"))

config = dict(
    binario = dict(
        polipo=dict(
            id=1,
            color="#fc0000",
            categories=["polipo"],
        ),
        altro=dict(
            id=2,
            color="#0000fc",
            categories=["iperplasia semplice", "iperplasia complessa", "K", "EIN", "sinechie", "endometrio polipoide", "mioma"]
        )
    ),
    default = dict(
        focale=dict(
            id=1,
            color="#fc0000",
            categories=["polipo", "mioma"],
        ),
        disnormale=dict(
            id=2,
            color="#00fc00",
            categories=["endometrio polipoide", "iperplasia semplice", "iperplasia complessa"]
        ),
        oncologica=dict(
            id=3,
            color="#0000fc",
            categories=["EIN", "K"]
        ) 
    )
)

assert args.config in config
config = config[args.config]

new_categories = []
new_categories_map = dict()
for name, newcat in config.items():
    new_categories.append(dict(
        id=newcat["id"],
        name=name,
        supercategory="",
        color=newcat["color"],
        metadata=dict(),
        keypoint_colors=[]
    ))
    for oldcat_name in newcat["categories"]:
        for oldcat in dataset["categories"]:
            if oldcat["name"] == oldcat_name:
                new_categories_map[oldcat["id"]] = newcat["id"]

usable_images = []
new_annotations = []
for annotation in dataset["annotations"]:
    if annotation["category_id"] in new_categories_map.keys():
        annotation["category_id"] = new_categories_map[annotation["category_id"]]
        new_annotations.append(annotation)
        usable_images.append(annotation["image_id"])

new_images = []
for image in dataset["images"]:
    if image["id"] in usable_images:
        new_images.append(image)    


json.dump(dict(
    images=new_images,
    annotations=new_annotations,
    categories=new_categories
), open(dest_dataset_file, "w"), indent=2)
print("Wrote %s" % (dest_dataset_file, ))
