# Data credits for the v3 detector

`project/models/ev_detector_v3_sankalp.pt` was trained on the original Roboflow "Emergency vehicle" dataset
(1,065 images, CC BY 4.0) plus 442 new images from EV_Indian_Dataset_v1 (Wikimedia Commons, Flickr and frames of
Commons videos). Every new image keeps its own licence (mostly CC BY / CC BY-SA, some CC0, public domain and
GODL-India).

* `EV_Indian_Dataset_v1_manifest.csv`: one row per image with its source page, author, licence, licence URL and
  the changes made (resized, re-encoded, YOLO labels added). `split` says whether it was used for training (`train`)
  or kept out as the Indian test set (`test_indian`).
* `EV_Indian_Dataset_v1_LICENSES.md`: licence counts and what each licence asks of you.

If you publish the images themselves, credit each author as listed in the manifest and link the licence.
The full dataset (images + labels) is shared separately as EV_Indian_Dataset_v1 (3 zip parts).
