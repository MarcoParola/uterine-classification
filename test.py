import torch
import pytorch_lightning
import omegaconf

from sklearn.metrics import classification_report

from src.data.masked_classification.datamodule import UterineClassificationMaskedDataModule
from src.data.segmentation.datamodule import UterineSegmentationDataModule
from src.models.classification import UterineClassifierModule
from src.models.saliency_classification import UterineSaliencyClassifierModule

from src.data.classification.datamodule import UterineClassificationDataModule
from src.data.classification.dataset import UterineClassificationDataset
from src.data.saliency_classification.datamodule import UterineClassificationSaliencyDataModule
from src.data.saliency_classification.dataset import UterineClassificationSaliencyDataset
from src.models.segmentation import FcnSegmentationNet, DeeplabSegmentationNet
from src.saliency.grad_cam import UterineGradCam
from src.saliency.lime import UterineLime
from src.saliency.shap import UterineShap
import hydra

from src.utils import *
from src.log import get_loggers


def predict(trainer, model, data, saliency_map_flag, task, classification_mode):

    if task == 'c' or task == 'classification':
        trainer.test(model, data.test_dataloader())
        if saliency_map_flag == "grad-cam":
            predictions = trainer.predict(model, data)
            predictions = torch.cat(predictions, dim=0)
            predictions = torch.argmax(predictions, dim=1)
            UterineGradCam.generate_saliency_maps_grad_cam(model, data.test_dataloader(), predictions, classification_mode)

    elif task == 's' or task == 'segmentation':
        trainer.test(model, data)

@hydra.main(version_base=None, config_path="./config", config_name="config")
def main(cfg):
    # this main load a checkpoint saved and perform test on it

    # save the passed version number before overwriting the configuration with training configuration
    version = str(cfg.checkpoint.version)
    # save the passed saliency map generation method before overwriting the configuration with training configuration
    saliency_map_method = cfg.generate_map
    # save the passed logging method before overwriting the configuration with training configuration
    loggers = get_loggers(cfg)
    # find the hydra_run_timestamp.txt file
    f = open('./logs/uterine/version_' + version + '/hydra_run_timestamp.txt', "r")
    # read the timestamp inside hydra_run_timestamp.txt
    timestamp = f.read()
    # use the timestamp to build the path to hydra configuration
    path = './outputs/' + timestamp + '/.hydra/config.yaml'
    # load the configuration used during training
    cfg = omegaconf.OmegaConf.load(path)

    # to test is needed: trainer, model and data
    # trainer
    trainer = pytorch_lightning.Trainer(
        logger=loggers,
        # callbacks=callbacks,  shouldn't need callbacks in test
        accelerator=cfg.train.accelerator,
        devices=cfg.train.devices,
        log_every_n_steps=1,
        max_epochs=cfg.train.max_epochs,
        # gradient_clip_val=0.1,
        # gradient_clip_algorithm="value"
    )

    model = None
    data = None

    if cfg.task == 'c' or cfg.task == 'classification':
        # whole classification
        if cfg.classification_mode == 'whole':
            # model
            # get the model already trained from checkpoints, default checkpoint is version_0, otherwise specify by cli
            model = UterineClassifierModule.load_from_checkpoint(get_last_checkpoint(version))
            model.eval()

            # data
            train_img_tranform, val_img_tranform, test_img_tranform, img_tranform = get_transformations(cfg)
            data = UterineClassificationDataModule(
                train=cfg.dataset.train,
                val=cfg.dataset.val,
                test=cfg.dataset.test,
                batch_size=cfg.train.batch_size,
                train_transform=train_img_tranform,
                val_transform=val_img_tranform,
                test_transform=test_img_tranform,
                transform=img_tranform
            )

        elif cfg.classification_mode == 'saliency':
            model = UterineSaliencyClassifierModule.load_from_checkpoint(get_last_checkpoint(version))
            model.eval()

            # data
            train_img_tranform, val_img_tranform, test_img_tranform, img_tranform = get_transformations(cfg)
            data = UterineClassificationSaliencyDataModule(
                train=cfg.dataset.train,
                val=cfg.dataset.val,
                test=cfg.dataset.test,
                batch_size=cfg.train.batch_size,
                train_transform=train_img_tranform,
                val_transform=val_img_tranform,
                test_transform=test_img_tranform,
                transform=img_tranform
            )

        elif cfg.classification_mode == 'masked':
            model = UterineClassifierModule.load_from_checkpoint(get_last_checkpoint(version))
            model.eval()

            train_img_tranform, val_img_tranform, test_img_tranform, img_tranform = get_transformations(cfg)
            data = UterineClassificationMaskedDataModule(
                sgm_type=cfg.sgm_type,
                segmenter=cfg.model_seg,
                train=cfg.dataset.train,
                val=cfg.dataset.val,
                test=cfg.dataset.test,
                batch_size=cfg.train.batch_size,
                train_transform=train_img_tranform,
                val_transform=val_img_tranform,
                test_transform=test_img_tranform,
                transform=img_tranform
            )

    elif cfg.task == 's' or cfg.task == 'segmentation':
        train_img_tranform, val_img_tranform, test_img_tranform, img_tranform = get_transformations(cfg)
        data = UterineSegmentationDataModule(
            train=cfg.dataset.train,
            val=cfg.dataset.val,
            test=cfg.dataset.test,
            batch_size=cfg.train.batch_size,
            train_transform=train_img_tranform,
            val_transform=val_img_tranform,
            test_transform=test_img_tranform,
            transform=img_tranform
        )
        if cfg.model_seg == 'fcn':
            model = FcnSegmentationNet.load_from_checkpoint(get_last_checkpoint(version))
            model.sgm_type = cfg.sgm_type
        elif cfg.model_seg == 'deeplab':
            model = DeeplabSegmentationNet.load_from_checkpoint(get_last_checkpoint(version))
            model.sgm_type = cfg.sgm_type

        model.eval()

    predict(trainer, model, data, saliency_map_method, cfg.task, cfg.classification_mode)




if __name__ == "__main__":
    main()
