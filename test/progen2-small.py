from transformers import AutoModelForCausalLM
from tokenizers import Tokenizer
import torch
import torch.nn.functional as F

# load model and tokenizer
model = AutoModelForCausalLM.from_pretrained("hugohrban/progen2-small", trust_remote_code=True)
tokenizer = Tokenizer.from_pretrained("hugohrban/progen2-small")
tokenizer.no_padding()

# prepare input
prompt = "1MEVVIVTGMSGAGK"
input_ids = torch.tensor(tokenizer.encode(prompt).ids).to(model.device)

# forward pass
logits = model(input_ids).logits

# print output probabilities
next_token_logits = logits[-1, :]
next_token_probs = F.softmax(next_token_logits, dim=-1)
for i in range(tokenizer.get_vocab_size(with_added_tokens=False)):
    print(f"{tokenizer.id_to_token(i)}: {100 * next_token_probs[i].item():.2f} %")
