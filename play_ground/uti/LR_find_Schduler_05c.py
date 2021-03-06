
#################################################
### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
#################################################
# file to edit: dev_nb/05c_LR_Scheduler.ipynb
from uti.newLeaner_05b import *

class Recorder(Callback):
    _order = 1

    def __init__(self,beta=0.9):
        self.beta = beta
        self.losses, self.lrs = [], []
        self.avg_loss = 0.
        self.count = 0

    def begin_batch(self):
        self.count += 1

    def after_loss(self):
        if self.learn.in_train:
            with torch.no_grad():
                self.losses.append(self.smooth_loss())
                self.lrs.append(self.learn.opt.param_groups[0]['lr'])

    def smooth_loss(self):
        loss = self.learn.loss.item()
        self.avg_loss = self.avg_loss * self.beta + loss * (1-self.beta)
        smooth_loss = self.avg_loss / (1-self.beta ** self.count)
        return smooth_loss


    def plot_lr(self):
        plt.plot(self.lrs)

    def plot_loss(self):
        plt.plot(self.losses)

class LR_find(Callback):
    def begin_fit(self,start=1e-8,end=10.,beta=0.98):
        self.start, self.end, self.beta = start, end, beta
        self.current_lr = start
        self.ratio = (end / start) ** (1 / (len(self.learn.data.train_dl)-1))
        self.lr = []
        self.losses = []
        self.best_loss = 0.
        self.avg_loss = 0.
        self.smooth_loss = 0.
        self.batch_num = 0

    def begin_batch(self):
        self.batch_num += 1
        self.learn.opt.param_groups[0]['lr'] = self.current_lr


    def after_loss(self):
        self.loss = self.learn.loss
        self.avg_loss = self.avg_loss * self.beta + self.loss.data * (1 - self.beta)
        self.smooth_loss = self.avg_loss / (1 - self.beta ** self.batch_num) #debias
        if self.batch_num > 1 and self.smooth_loss > 4 * self.best_loss:
            raise CancelTrainException()
        if self.batch_num == 1 or self.best_loss > self.smooth_loss:
            self.best_loss = self.smooth_loss
            self.best_lr = self.current_lr
        self.losses.append(self.smooth_loss)
        self.lr.append(math.log10(self.current_lr))
        self.current_lr *= self.ratio


    def begin_validate(self):
        raise CancelTrainException()

class ParaScheduler(Callback):
    _order = 1
    def __init__(self,para_name,sched_func):
        self.para_name, self.sched_func = para_name, sched_func

    def set_param(self,pos):
        self.learn.opt.param_groups[0][self.para_name] = self.sched_func(pos)

    def begin_batch(self):
        if self.learn.in_train:

            #cbs[0] will always be TrainEvalCallback
            #TrainEval will have current pos, eg: 2.3 epochs
            #pos = current_epochs / total_epochs, eg: 20% of training

            pos = self.learn.cbs[0].n_epochs / self.learn.epochs
            self.set_param(pos)

from functools import partial
def annealer(f):
    def _inner(start, end): return partial(f, start, end)
    return _inner

@annealer
def sched_lin(start, end, pos): return start + pos*(end-start)

@annealer
def sched_cos(start, end, pos): return start + (1 + math.cos(math.pi*(1-pos))) * (end-start) / 2

@annealer
def sched_no(start, end, pos):  return start

@annealer
def sched_exp(start, end, pos): return start * (end/start) ** pos

#copied from class
def combine_scheds(pcts, scheds):
    assert sum(pcts) == 1.
    pcts = tensor([0] + pcts)
    assert torch.all(pcts >= 0)
    pcts = torch.cumsum(pcts, 0)
    def _inner(pos):
        idx = (pos >= pcts).nonzero().max()
        actual_pos = (pos-pcts[idx]) / (pcts[idx+1]-pcts[idx])
        return scheds[idx](actual_pos)
    return _inner