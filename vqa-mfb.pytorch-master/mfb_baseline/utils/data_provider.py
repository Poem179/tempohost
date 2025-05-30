# -*- coding: utf-8 -*-
import numpy as np
import re, json, random
import config
import torch.utils.data as data

QID_KEY_SEPARATOR = '/'
ZERO_PAD = '_PAD'
GLOVE_EMBEDDING_SIZE = 300
class VQADataProvider:

    def __init__(self, opt, folder='./result', batchsize=64, max_length=15, mode='train'):
        self.opt = opt
        self.batchsize = batchsize
        self.d_vocabulary = None
        self.batch_index = None
        self.batch_len = None
        self.rev_adict = None
        self.max_length = max_length
        self.mode = mode
        self.qdic, self.adic = VQADataProvider.load_data(mode)

        with open('./%s/vdict.json'%folder,'r') as f:
            self.vdict = json.load(f)
        with open('./%s/adict.json'%folder,'r') as f:
            self.adict = json.load(f)


    @staticmethod
    def load_vqa_json(data_split):
        """
        Parses the question and answer json files for the given data split. 
        Returns the question dictionary and the answer dictionary.
        """
        qdic, adic = {}, {}

        with open(config.DATA_PATHS[data_split]['ques_file'], 'r') as f:
            qdata = json.load(f)['questions']
            for q in qdata:
                qdic[data_split + QID_KEY_SEPARATOR + str(q['question_id'])] = \
                    {'qstr': q['question'], 'iid': q['image_id']}

        if 'test' not in data_split:
            with open(config.DATA_PATHS[data_split]['ans_file'], 'r') as f:
                adata = json.load(f)['annotations']
                for a in adata:
                    adic[data_split + QID_KEY_SEPARATOR + str(a['question_id'])] = \
                        a['answers']

        print('parsed', len(qdic), 'questions for', data_split)
        return qdic, adic

    @staticmethod
    def load_genome_json():
        """
        Parses the genome json file. Returns the question dictionary and the
        answer dictionary.
        """
        qdic, adic = {}, {}

        with open(config.DATA_PATHS['genome']['genome_file'], 'r') as f:
            qdata = json.load(f)
            for q in qdata:
                key = 'genome' + QID_KEY_SEPARATOR + str(q['id'])
                qdic[key] = {'qstr': q['question'], 'iid': q['image']}
                adic[key] = [{'answer': q['answer']}]

        print('parsed', len(qdic), 'questions for genome')
        return qdic, adic

    @staticmethod
    def load_data(data_split_str):
        all_qdic, all_adic = {}, {}
        for data_split in data_split_str.split('+'):
            assert data_split in config.DATA_PATHS.keys(), 'unknown data split'
            if data_split == 'genome':
                qdic, adic = VQADataProvider.load_genome_json()
                all_qdic.update(qdic)
                all_adic.update(adic)
            else:
                qdic, adic = VQADataProvider.load_vqa_json(data_split)
                all_qdic.update(qdic)
                all_adic.update(adic)
        return all_qdic, all_adic

    def getQuesIds(self):
        return self.qdic.keys()

    def getStrippedQuesId(self, qid):
        return qid.split(QID_KEY_SEPARATOR)[1]

    def getImgId(self,qid):
        return self.qdic[qid]['iid']

    def getQuesStr(self,qid):
        return self.qdic[qid]['qstr']

    def getAnsObj(self,qid):
        if self.mode == 'test-dev' or self.mode == 'test':
            return -1
        return self.adic[qid]

    @staticmethod
    def seq_to_list(s):
        t_str = s.lower()
        for i in [r'\?',r'\!',r'\'',r'\"',r'\$',r'\:',r'\@',r'\(',r'\)',r'\,',r'\.',r'\;']:
            t_str = re.sub( i, '', t_str)
        for i in [r'\-',r'\/']:
            t_str = re.sub( i, ' ', t_str)
        q_list = re.sub(r'\?','',t_str.lower()).split(' ')
        q_list = filter(lambda x: len(x) > 0, q_list)
        return q_list

    def extract_answer(self,answer_obj):
        """ Return the most popular answer in string."""
        if self.mode == 'test-dev' or self.mode == 'test':
            return -1
        answer_list = [ answer_obj[i]['answer'] for i in xrange(10)]
        dic = {}
        for ans in answer_list:
            if dic.has_key(ans):
                dic[ans] +=1
            else:
                dic[ans] = 1
        max_key = max((v,k) for (k,v) in dic.items())[1]
        return max_key

    def extract_answer_prob(self,answer_obj):
        """ Return the most popular answer in string."""
        if self.mode == 'test-dev' or self.mode == 'test':
            return -1

        answer_list = [ ans['answer'] for ans in answer_obj]
        prob_answer_list = []
        for ans in answer_list:
            if self.adict.has_key(ans):
                prob_answer_list.append(ans)
    def extract_answer_list(self,answer_obj):
        answer_list = [ ans['answer'] for ans in answer_obj]
        prob_answer_vec = np.zeros(self.opt.NUM_OUTPUT_UNITS)
        for ans in answer_list:
            if self.adict.has_key(ans):
                index = self.adict[ans]
                prob_answer_vec[index] += 1
        return prob_answer_vec / np.sum(prob_answer_vec)
 
        if len(prob_answer_list) == 0:
            if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
                return 'hoge'
            else:
                raise Exception("This should not happen.")
        else:
            return random.choice(prob_answer_list)
 
    def qlist_to_vec(self, max_length, q_list):
        """
        Converts a list of words into a format suitable for the embedding layer.

        Arguments:
        max_length -- the maximum length of a question sequence
        q_list -- a list of words which are the tokens in the question

        Returns:
        qvec -- A max_length length vector containing one-hot indices for each word
        cvec -- A max_length length sequence continuation indicator vector
        """
        qvec = np.zeros(max_length)
        cvec = np.zeros(max_length)
        """  pad on the left   """
        # for i in xrange(max_length):
        #     if i < max_length - len(q_list):
        #         cvec[i] = 0
        #     else:
        #         w = q_list[i-(max_length-len(q_list))]
        #         # is the word in the vocabulary?
        #         if self.vdict.has_key(w) is False:
        #             w = ''
        #         qvec[i] = self.vdict[w]
        #         cvec[i] = 0 if i == max_length - len(q_list) else 1
        """  pad on the right   """
        for i in xrange(max_length):
            if i >= len(q_list):
                pass
            else:
                w = q_list[i]
                if self.vdict.has_key(w) is False:
                    w = ''
                qvec[i] = self.vdict[w]
                cvec[i] = 1 
        return qvec, cvec
 
    def answer_to_vec(self, ans_str):
        """ Return answer id if the answer is included in vocabulary otherwise '' """
        if self.mode =='test-dev' or self.mode == 'test':
            return -1

        if self.adict.has_key(ans_str):
            ans = self.adict[ans_str]
        else:
            ans = self.adict['']
        return ans
 
    def vec_to_answer(self, ans_symbol):
        """ Return answer id if the answer is included in vocabulary otherwise '' """
        if self.rev_adict is None:
            rev_adict = {}
            for k,v in self.adict.items():
                rev_adict[v] = k
            self.rev_adict = rev_adict

        return self.rev_adict[ans_symbol]
 
    def create_batch(self,qid_list):

        qvec = (np.zeros(self.batchsize*self.max_length)).reshape(self.batchsize,self.max_length)
        cvec = (np.zeros(self.batchsize*self.max_length)).reshape(self.batchsize,self.max_length)
        ivec = (np.zeros(self.batchsize*2048)).reshape(self.batchsize,2048)
        if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
            avec = np.zeros(self.batchsize)
        else:
            avec = np.zeros((self.batchsize, self.opt.NUM_OUTPUT_UNITS))

        for i,qid in enumerate(qid_list):

            # load raw question information
            q_str = self.getQuesStr(qid)
            q_ans = self.getAnsObj(qid)
            q_iid = self.getImgId(qid)

            # convert question to vec
            q_list = VQADataProvider.seq_to_list(q_str)
            t_qvec, t_cvec = self.qlist_to_vec(self.max_length, q_list)

            try:
                qid_split = qid.split(QID_KEY_SEPARATOR)
                data_split = qid_split[0]
                if data_split == 'genome':
                    t_ivec = np.load(config.DATA_PATHS['genome']['features_prefix'] + str(q_iid) + '.jpg.npz')['x']
                else:
                    t_ivec = np.load(config.DATA_PATHS[data_split]['features_prefix'] + str(q_iid).zfill(12) + '.jpg.npz')['x']
                t_ivec = ( t_ivec / np.sqrt((t_ivec**2).sum()) )
            except:
                t_ivec = 0.
                print('data not found for qid : ', q_iid,  self.mode0)
             
            # convert answer to vec
            if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
                q_ans_str = self.extract_answer(q_ans)
                t_avec = self.answer_to_vec(q_ans_str)
            else:
                t_avec = self.extract_answer_list(q_ans)
 
            qvec[i,...] = t_qvec
            cvec[i,...] = t_cvec
            ivec[i,...] = t_ivec
            avec[i,...] = t_avec

        return qvec, cvec, ivec, avec

 
    def get_batch_vec(self):
        if self.batch_len is None:
            self.n_skipped = 0
            qid_list = self.getQuesIds()
            random.shuffle(qid_list)
            self.qid_list = qid_list
            self.batch_len = len(qid_list)
            self.batch_index = 0
            self.epoch_counter = 0

        def has_at_least_one_valid_answer(t_qid):
            answer_obj = self.getAnsObj(t_qid)
            answer_list = [ans['answer'] for ans in answer_obj]
            for ans in answer_list:
                if self.adict.has_key(ans):
                    return True

        counter = 0
        t_qid_list = []
        t_iid_list = []
        while counter < self.batchsize:
            t_qid = self.qid_list[self.batch_index]
            t_iid = self.getImgId(t_qid)
            if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
                t_qid_list.append(t_qid)
                t_iid_list.append(t_iid)
                counter += 1
            elif has_at_least_one_valid_answer(t_qid):
                t_qid_list.append(t_qid)
                t_iid_list.append(t_iid)
                counter += 1
            else:
                self.n_skipped += 1 

            if self.batch_index < self.batch_len-1:
                self.batch_index += 1
            else:
                self.epoch_counter += 1
                qid_list = self.getQuesIds()
                random.shuffle(qid_list)
                self.qid_list = qid_list
                self.batch_index = 0
                print("%d questions were skipped in a single epoch" % self.n_skipped)
                self.n_skipped = 0

        t_batch = self.create_batch(t_qid_list)
        return t_batch + (t_qid_list, t_iid_list, self.epoch_counter)

class VQADataset(data.Dataset):

    def __init__(self, mode, batchsize, folder, opt):
        self.batchsize = batchsize 
        self.mode = mode 
        self.folder = folder 
        if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
            pass
        else:
            self.dp = VQADataProvider(opt, batchsize=self.batchsize, mode=self.mode, folder=self.folder)

    def __getitem__(self, index):
        if self.mode == 'val' or self.mode == 'test-dev' or self.mode == 'test':
            pass
        else:
            word, cont, feature, answer, _, _, epoch = self.dp.get_batch_vec()
        word_length = np.sum(cont, axis=1)
        return word, word_length, feature, answer, epoch

    def __len__(self):
        if self.mode == 'train':
            return 150000   # this number had better bigger than "maxiterations" which you set in config
