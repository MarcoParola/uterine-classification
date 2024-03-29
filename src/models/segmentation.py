import torch
import numpy as np
import torch.nn as nn
import math
from torchvision import models
import pytorch_lightning as pl
from pytorch_lightning import LightningModule

import torch.optim as optim
from src.metrics import SegmentationMetrics


class FcnSegmentationNet(LightningModule):
    '''
    This class implements a Fully Convolutional Network for segmentation.
    '''
    def __init__(self, num_classes=1, lr=5e-7, epochs=1000, len_dataset=0, batch_size=0, loss=nn.BCEWithLogitsLoss(), sgm_type="soft", sgm_threshold=0.5):
        super(FcnSegmentationNet, self).__init__()
        self.pretrained_model = models.segmentation.fcn_resnet50(pretrained=True)
        #sostituendo il quinto strato del classificatore del modello preaddestrato con un nuovo strato di convoluzione 
        #che trasformerà le 512 feature maps in un numero di canali uguale a num_classes.
        self.pretrained_model.classifier[4] = nn.Conv2d(512, num_classes, kernel_size=(1, 1), stride=(1, 1))

        self.lr = lr
        self.loss = loss
        self.sgm_type = sgm_type
        self.sgm_threshold = sgm_threshold
        self.epochs = epochs
        self.len_dataset = len_dataset
        self.batch_size = batch_size

    def forward(self, x):
        out = self.pretrained_model(x)['out']
        if self.sgm_type == 'hard':
            out = (out > self.sgm_threshold).float()
        return out

    def predict_step(self, batch, batch_idx):
        return self(batch[0])

    def training_step(self, batch, batch_idx):
        return self._common_step(batch, batch_idx, "train")

    def validation_step(self, batch, batch_idx):
        self._common_step(batch, batch_idx, "val") 
        
    def test_step(self, batch, batch_idx):
        #self._common_step(batch, batch_idx, "test")
        images, masks = batch
        outputs = self(images)

        loss = self.loss(outputs, masks)
        self.log('test_loss', loss)
        compute_met = SegmentationMetrics()
        met = compute_met(masks, outputs) # met is a list
        #return loss, met
        self.log_dict({'test_loss': loss, 'test_acc': met[0], 'test_dice': met[1], 'test_precision': met[2], 'test_specificity': met[3], 'test_recall': met[4], 'jaccard': met[5]})
        self.log('test_acc', met[0])
        self.log('test_dice', met[1])
        self.log('test_precision', met[2])
        self.log('test_specificity', met[3])
        self.log('test_recall', met[4])
        self.log('test_jaccard', met[5])

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=self.lr)
        sch = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr = 0.01, epochs=self.epochs, steps_per_epoch = int(math.ceil(self.len_dataset / self.batch_size)))
        return [optimizer], [sch]
        
    def _common_step(self, batch, batch_idx, stage):
        img, actual_mask = batch
        mask_predicted = self.pretrained_model(img)['out']
        loss = self.loss(mask_predicted, actual_mask)
        self.log(f"{stage}_loss", loss, on_step=True)
        return loss



class DeeplabSegmentationNet(pl.LightningModule):
    '''
    This class implements a DeepLabV3 model for segmentation.
    '''
    def __init__(self, num_classes=1, lr=5e-7, epochs=1000, len_dataset=0, batch_size=0, loss=nn.BCEWithLogitsLoss(), pretrained=True, sgm_type="hard", sgm_threshold=0.5):
        super().__init__()
        self.save_hyperparameters()
        self.model = models.segmentation.deeplabv3_resnet50(pretrained=pretrained)
        # Questa riga modifica l'ultimo strato del classificatore del modello DeepLabV3 per avere num_classes canali di uscita. 
        # Questo è necessario perché il modello preaddestrato avrà un numero diverso di canali nell'ultimo strato a seconda del dataset su cui è stato preaddestrato. 
        # Qui si adatta il modello alle esigenze specifiche del problema di segmentazione.
        self.model.classifier[4] = torch.nn.Conv2d(256, num_classes, kernel_size=(1, 1), stride=(1, 1)) # TODO fai check sul valore 256
        self.num_classes = num_classes
        self.criterion = loss
        self.lr = lr
        self.sgm_type = sgm_type
        self.sgm_threshold = sgm_threshold
        self.epochs = epochs
        self.len_dataset = len_dataset
        self.batch_size = batch_size

    #To run data through your model only. Called with output = model(input_data)
    def forward(self, x):
        out = self.model(x)['out']
        out = (out > self.sgm_threshold).float()
        return out

    def predict_soft_mask(self, x):
        out = self.model(x)['out']
        return out

    #la variabile batch è fornita automaticamente dal DataLoader
    def training_step(self, batch, batch_idx):
        images, masks = batch
        outputs = self.model(images)['out']
        loss = self.criterion(outputs, masks)
        self.log('train_loss', loss)
        return loss

    def validation_step(self, batch, batch_idx):
        images, masks = batch
        outputs = self.model(images)['out']
        loss = self.criterion(outputs, masks)
        self.log('val_loss', loss)
        return loss

    def test_step(self, batch, batch_idx):
        images, masks = batch
        outputs = self(images)

        loss = self.criterion(outputs, masks)
        self.log('test_loss', loss)
        compute_met = SegmentationMetrics()
        met = compute_met(masks, outputs) # met is a list
        #return loss, met
        self.log_dict({'test_loss': loss, 'test_acc': met[0], 'test_dice': met[1], 'test_precision': met[2], 'test_specificity': met[3], 'test_recall': met[4], 'jaccard': met[5]})
        self.log('test_acc', met[0])
        self.log('test_dice', met[1])
        self.log('test_precision', met[2])
        self.log('test_specificity', met[3])
        self.log('test_recall', met[4])
        self.log('test_jaccard', met[5])

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=self.lr)
        sch = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=0.01, epochs=self.epochs, steps_per_epoch=int(math.ceil(self.len_dataset / self.batch_size)))
        return [optimizer], [sch]
         