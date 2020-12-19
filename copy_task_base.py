import numpy as np
import math
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import sys
from time import time

# print(np.__version__)
from torch.backends import cudnn

print(torch.__version__)

# Set the seed of PRNG manually for reproducibility
seed = 1234
torch.manual_seed(seed)
np.random.seed(seed)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def cross_entropy_formula(step):
    return (10 * np.log(8)) / (step + 20)


class MLP(nn.Module):

    def __init__(self, in_features, out_features):
        super(MLP, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        k = 1 / in_features
        bound = math.sqrt(k)
        # toch.rand returns a tensor samples uniformly in [0, 1).
        # we scaling it to [l = -bound, r = bound] using the formula: (l - r) * torch.rand(x, y) + r
        self.W = (-2 * bound) * torch.rand(out_features, in_features).cuda(device) + bound

    def forward(self, x):
        _, input_num = x.shape
        if input_num != self.in_features:
            sys.exit(f'Wrong x size: {x}')
        y = x @ self.W.t()
        return y


class RNN(nn.Module):

    def __init__(self, in_features, out_features, non_linearity="tanh"):
        super(RNN, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.non_linearity = non_linearity
        k = 1 / out_features
        bound = math.sqrt(k)
        # toch.rand returns a tensor samples uniformly in [0, 1).
        # we scaling it to [l = -bound, r = bound] using the formula: (l - r) * torch.rand(x, y) + r
        self.W = (-2 * bound) * torch.rand(out_features, in_features).cuda(device) + bound
        self.U = (-2 * bound) * torch.rand(out_features, out_features).cuda(device) + bound

    def forward(self, x, b_prev=None):

        # check validity of x
        _, input_num = x.shape
        if input_num != self.in_features:
            sys.exit(f'Wrong x size: {x}')

        # check validity of b_prev
        if b_prev is not None:
            _, output_num = b_prev.shape
            if output_num != self.out_features:
                sys.exit(f'Wrong b size: {b_prev}')
        else:
            b_prev = torch.zeros(x.shape[0], self.out_features)
        a = (x @ self.W.t()) + (b_prev @ self.U.t())

        if self.non_linearity == "tanh":
            b = torch.tanh(a)
        else:
            b = torch.relu(a)

        return b


class LSTM(nn.Module):

    def __init__(self, in_features, out_features):
        super(LSTM, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        k = 1 / out_features
        bound = math.sqrt(k)
        # toch.rand returns a tensor samples uniformly in [0, 1).
        # we scaling it to [l = -bound, r = bound] using the formula: (l - r) * torch.rand(x, y) + r
        self.Wi = (-2 * bound) * torch.rand(out_features, in_features).cuda(device) + bound
        self.Ui = (-2 * bound) * torch.rand(out_features, out_features).cuda(device) + bound
        self.Wf = (-2 * bound) * torch.rand(out_features, in_features).cuda(device) + bound
        self.Uf = (-2 * bound) * torch.rand(out_features, out_features).cuda() + bound
        self.Wg = (-2 * bound) * torch.rand(out_features, in_features).cuda() + bound
        self.Ug = (-2 * bound) * torch.rand(out_features, out_features).cuda() + bound
        self.Wo = (-2 * bound) * torch.rand(out_features, in_features).cuda() + bound
        self.Uo = (-2 * bound) * torch.rand(out_features, out_features).cuda() + bound

    def forward(self, x, state=None):
        h_prev = state[0] if state is not None else None
        c_prev = state[1] if state is not None else None

        # check validity of x
        _, input_num = x.shape
        if input_num != self.in_features:
            sys.exit(f'Wrong x size: {x}')

        # check validity of b_prev
        # if h_prev is not None:
        #     _, output_num = h_prev.shape
        #     if output_num != self.out_features:
        #         sys.exit(f'Wrong h size: {h_prev}')
        if h_prev is None or c_prev is None:
            h_prev = torch.zeros(x.shape[0], self.out_features)
            c_prev = torch.zeros(x.shape[0], self.out_features)

        activation_func = nn.Sigmoid()
        i = activation_func((x @ self.Wi.t()) + (h_prev @ self.Ui.t()))
        f = activation_func((x @ self.Wf.t()) + (h_prev @ self.Uf.t()))
        g = torch.tanh((x @ self.Wg.t()) + (h_prev @ self.Ug.t()))
        o = activation_func((x @ self.Wo.t()) + (h_prev @ self.Uo.t()))
        c = (f * c_prev) + (i * g)
        h = o * torch.tanh(c_prev)
        return h, c


# Copy data
def copy_data(T, K, batch_size):
    seq = np.random.randint(1, high=9, size=(batch_size, K))
    zeros1 = np.zeros((batch_size, T))
    zeros2 = np.zeros((batch_size, K - 1))
    zeros3 = np.zeros((batch_size, K + T))
    marker = 9 * np.ones((batch_size, 1))

    x = torch.LongTensor(np.concatenate((seq, zeros1, marker, zeros2), axis=1))
    y = torch.LongTensor(np.concatenate((zeros3, seq), axis=1))

    return x, y


# one hot encoding
def onehot(out, input):
    out.zero_()
    in_unsq = torch.unsqueeze(input, 2)
    out.scatter_(2, in_unsq, 1)


# Class for handling copy data
class Model(nn.Module):
    def __init__(self, m, k, architecture=MLP):
        super(Model, self).__init__()

        self.m = m
        self.k = k
        self.architecture = architecture
        self.rnn = architecture(m + 1, k).cuda(device)
        self.V = nn.Linear(k, m).cuda(device)

        # loss for the copy data
        self.loss_func = nn.CrossEntropyLoss()

    def forward(self, inputs):
        state = torch.zeros(inputs.size(0), self.k, requires_grad=False).cuda()

        outputs = []
        for input in torch.unbind(inputs, dim=1):
            if self.architecture == MLP:
                state = self.rnn(input)
            elif self.architecture == RNN:
                state = self.rnn(input, state)
            elif self.architecture == LSTM:
                state = self.rnn(input, state)[1]

            outputs.append(self.V(state))

        return torch.stack(outputs, dim=1)

    def loss(self, logits, y):
        return self.loss_func(logits.view(-1, 9), y.view(-1))


T = 8
K = 3

batch_size = 128
iter = 5000
n_train = iter * batch_size
n_classes = 9
hidden_size = 64
n_characters = n_classes + 1
lr = 1e-3
print_every = 100


def main():
    xs = np.array([])
    ys_loss_mlp = np.array([])
    ys_loss_rnn = np.array([])
    ys_loss_lstm = np.array([])
    ys = np.array([])
    # create the training data
    X, Y = copy_data(T, K, n_train)
    print('{}, {}'.format(X.shape, Y.shape))
    plt.imshow(X[:3])
    plt.show()
    X = X.cuda()
    Y = Y.cuda()
    ohX = torch.FloatTensor(batch_size, T + 2 * K, n_characters).cuda()
    onehot(ohX, X[:batch_size])
    # print(ohX)
    # print('{}, {}'.format(X[:batch_size].shape, ohX.shape))
    model_MLP = Model(n_classes, hidden_size, MLP)
    model_RNN = Model(n_classes, hidden_size, RNN)
    model_LSTM = Model(n_classes, hidden_size, LSTM)
    print(device)
    model_MLP.cuda(device)
    model_RNN.cuda(device)
    model_LSTM.cuda(device)

    cudnn.benchmark = True
    cudnn.fastest = True
    model_MLP.train()
    model_RNN.train()
    model_LSTM.train()
    opt_MLP = torch.optim.RMSprop(model_MLP.parameters(), lr=lr)
    opt_RNN = torch.optim.RMSprop(model_RNN.parameters(), lr=lr)
    opt_LSTM = torch.optim.RMSprop(model_LSTM.parameters(), lr=lr)

    print("Baseline Loss {:.3f}".format(cross_entropy_formula(1)))

    t_0 = time()
    for step in range(iter):
        # xs.append(step)
        # ys.append(cross_entropy_formula(step))

        xs = np.append(xs, step)
        ys = np.append(ys, cross_entropy_formula(T+K-1))
        bX = X[step * batch_size: (step + 1) * batch_size]
        bY = Y[step * batch_size: (step + 1) * batch_size]

        onehot(ohX, bX)

        opt_MLP.zero_grad()
        opt_RNN.zero_grad()
        opt_LSTM.zero_grad()
        logits_MLP = model_MLP(ohX)
        logits_RNN = model_RNN(ohX)
        logits_LSTM = model_LSTM(ohX)
        loss_MLP = model_MLP.loss(logits_MLP, bY)
        loss_RNN = model_MLP.loss(logits_RNN, bY)
        loss_LSTM = model_MLP.loss(logits_LSTM, bY)
        loss_MLP.backward()
        loss_RNN.backward()
        loss_LSTM.backward()
        opt_MLP.step()
        opt_RNN.step()
        opt_LSTM.step()

        ys_loss_mlp = np.append(ys_loss_mlp, loss_MLP.item())
        ys_loss_rnn = np.append(ys_loss_rnn, loss_RNN.item())
        ys_loss_lstm = np.append(ys_loss_lstm, loss_LSTM.item())

        if step % print_every == 0:
            print('Step={}, Loss={:.4f}'.format(step, loss_MLP.item()))

    t_1 = time()
    print("training took : {:.3f}".format(t_1 - t_0))
    plt.plot(xs, ys, '--g', label='Baseline')
    plt.plot(xs, ys_loss_mlp, '-m', label='MLP')
    plt.plot(xs, ys_loss_rnn, '-y', label='RNN')
    plt.plot(xs, ys_loss_lstm, '-c', label='LSTM')
    plt.title('{} Time lag'.format(T + K - 1))
    plt.legend()
    plt.xlabel('Training steps')
    plt.ylabel('Loss')
    plt.show()


if __name__ == "__main__":
    main()
