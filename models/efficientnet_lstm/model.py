import torch
from torch import nn
import torchvision.models as models
import torch.nn.functional as F
from models.efficientnet.net import Net

class Identity(nn.Module):
    def __init__(self):
        super(Identity, self).__init__()
        
    def forward(self, x):
        return x

class EfficientFeatures(nn.Module):
    def __init__(self, model_name, model_dir):
        super(EfficientFeatures, self).__init__()
        self.model = Net(model_name,False)
        checkpoint = torch.load(model_dir)
        self.model.load_state_dict(checkpoint['model'])
        self.model._fc = Identity()
        
    def forward(self, x):
        
        x = self.model(x)
        return x
    
class ResCNNEncoder(nn.Module):
    def __init__(self, model_name, model_dir):
        super(ResCNNEncoder, self).__init__()
        
        self.net = EfficientFeatures(model_name, model_dir)
        
    def forward(self, x):
        x = self.net(x)
        return x
    
class DecoderRNN(nn.Module):
    def __init__(self, input_size):
        super(DecoderRNN, self).__init__()
        
        self.LSTM = nn.LSTM(
            input_size=input_size,
            hidden_size=512,
            num_layers=2,
            dropout=0.3,
            batch_first=True,       # input & output will has batch size as 1s dimension. e.g. (batch, time_step, input_size)
            bidirectional=True
        )

#         self.fc1 = nn.Linear(1024, 512)
        self.fc1 = nn.Linear(512*2, 1)

    def forward(self, x):
        
#         self.LSTM.flatten_parameters()
        x, (h_n, h_c) = self.LSTM(x, None)
        x = self.fc1(x)
        
    
#         x = self.fc1(RNN_out[:, -1, :])   # choose RNN_out at the last time step
#         x = F.relu(x)
#         x = F.dropout(x, p=0.1, training=self.training)
#         x = self.fc2(x)

        return x[:, -1, :]
    
class SequenceModelEfficientNet(nn.Module):
    def __init__(self, model_name, model_dir):
        super(SequenceModelEfficientNet, self).__init__()

        self.encoder_model = ResCNNEncoder(model_name, model_dir)
        for param in self.encoder_model.parameters():
            param.requires_grad = False
        if "b7" in model_name:
            input_size = 2560
        else:
            input_size = 2304
        self.decoder_model = DecoderRNN(input_size)

    def forward(self, x):
        batch_size, timesteps, C, H, W = x.size()
        with torch.no_grad():
            x = x.view(batch_size * timesteps, C, H, W)
            x = self.encoder_model(x)
        x = x.view(batch_size, timesteps, -1)
        x = F.dropout(x, p=0.4, training=self.training)
        x = self.decoder_model(x)
        return x