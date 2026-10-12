# Dataset audit

## Source and provenance

Audited the provided archive, `Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip`, without extracting it into the repository. Its embedded README identifies Roboflow Universe project **Drowning Detection And Prevention In Swimming Pools**, workspace `yashwanee-tetar-jm88u`, version 3, export date July 12, 2023, and license **CC BY 4.0**. The dataset page is [Roboflow Universe v3](https://universe.roboflow.com/yashwanee-tetar-jm88u/drowning-detection-and-prevention-in-swimming-pools/dataset/3). Roboflow lists 8,925 images (7,358 train / 1,046 valid / 521 test), while the supplied archive has only **8,352** (6,785 / 1,046 / 521). The archive is missing 573 training images compared with the version page; the discrepancy is unresolved.

## Contents checked

| Split | Images | Label files | Objects by class ID (0–6) |
|---|---:|---:|---|
| Train | 6,785 | 6,785 | 1,351; 336; 3,118; 3,632; 1,772; 508; 3,542 |
| Validation | 1,046 | 1,046 | 171; 69; 465; 630; 529; 89; 704 |
| Test | 521 | 521 | 98; 36; 200; 285; 131; 31; 327 |
| **Total** | **8,352** | **8,352** | **18,024 objects** |

The format is YOLO detection text labels with normalized center-x, center-y, width and height. Every included image has a same-split label file, and every label file has an image. OpenCV successfully decoded all 8,352 images. No empty labels, malformed rows, invalid normalized values, out-of-range class IDs, or boxes crossing image edges were found. Exact SHA-256 comparison found **91 duplicate-content groups (91 excess duplicate images)**; **37 duplicate-content groups cross split boundaries**, including train/test. This leaks exact samples into evaluation. Near-duplicates and source-video/session overlap were not checked.

## Class mapping

`data.yaml` defines seven case-sensitive names in this order:

| ID | Name | Objects |
|---:|---|---:|
| 0 | Drowning | 1,620 |
| 1 | Out of Water | 441 |
| 2 | Swimming | 3,783 |
| 3 | drowning | 4,547 |
| 4 | out of water | 2,432 |
| 5 | person | 628 |
| 6 | swimming | 4,573 |

Three pairs differ only by capitalization and appear semantically duplicative. This audit does **not** merge them because that would alter labels and require recorded remapping plus renewed evaluation. The class imbalance is material. The export README also mentions augmentation from source images; no source identifiers are supplied to verify whether variants or video frames cross splits.

## Evaluation decision

The supplied `test` directory is **not an independent holdout** because of the 37 verified cross-split duplicate groups. Do not cite test metrics from this archive as independent performance. The project scripts print this limitation beside test evaluation. A defensible next evaluation needs duplicate-group removal/assignment, source-video grouping where source metadata exists, a fixed independent pool-video set, and a written remapping decision for the case-only class duplicates. The scripts retain the supplied files and create a separate corrected YAML; they do not silently edit data or labels.

## Additional public dataset candidate

| Field | CADDY Underwater Stereo-Vision / Diver Pose dataset |
|---|---|
| Publisher/authors | CADDY project; Constructor University Robotics group and collaborators |
| Source | [Project data page](https://robotics.constructor.university/code-data/datacode-diver-pose-estimation/); [paper DOI 10.3390/jmse7010016](https://doi.org/10.3390/jmse7010016) |
| Size/type | Project page describes 12,000 stereo image pairs synchronized with IMU-based diver body-pose measurements. The paper describes additional gesture and free-swimming subsets. Sequence/video count was not verified. |
| Format/labels | Rectified stereo imagery, IMU measurements/pose information; not a YOLO drowning-event annotation set. Exact package formats are described by the authors' paper/download material. |
| License/access | The paper is CC BY 4.0; this does not by itself prove the dataset files have the same license. Dataset-specific license was not verified. The linked `caddian.eu` download host timed out when checked; manual access may be required. |
| Fit | Potential auxiliary research for underwater appearance, pose and tracking robustness only. It contains divers with gear in underwater HRI trials, not pool swimmers or drowning events, so it must not train drowning risk labels or be merged with the Roboflow classes. |

This candidate is documented, not selected or downloaded. For temporal risk training, use a newly annotated, ethically sourced pool-video set with source-video IDs and independent group-level splits. The Roboflow detection labels alone are not temporal behavior labels.

## Reproduce the audit

```powershell
python tools/audit_dataset.py "C:\Users\DELL\Downloads\Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip" --output artifacts/dataset_audit.json
```

The JSON output is not committed because it may include archive-local names and is reproducible from the downloaded archive.
