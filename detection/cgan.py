"""
Conditional GAN (CGAN) and Tabular Diffusion for synthetic attack generation.
"""

import logging
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger("detection.cgan")


class CGANGenerator(nn.Module):
    def __init__(self, latent_dim: int = 10, num_classes: int = 6, feature_dim: int = 11):
        super().__init__()
        self.class_embed = nn.Embedding(num_classes, 10)
        self.net = nn.Sequential(
            nn.Linear(latent_dim + 10, 128),
            nn.LeakyReLU(0.2),
            nn.Linear(128, 64),
            nn.LeakyReLU(0.2),
            nn.Linear(64, feature_dim),
            nn.Tanh(),
        )
    
    def forward(self, z: torch.Tensor, labels: torch.Tensor):
        c_emb = self.class_embed(labels)
        x = torch.cat([z, c_emb], dim=1)
        return self.net(x)


class CGANDiscriminator(nn.Module):
    def __init__(self, num_classes: int = 6, feature_dim: int = 11):
        super().__init__()
        self.class_embed = nn.Embedding(num_classes, 10)
        self.net = nn.Sequential(
            nn.Linear(feature_dim + 10, 64),
            nn.LeakyReLU(0.2),
            nn.Linear(64, 1),
        )
    
    def forward(self, x: torch.Tensor, labels: torch.Tensor):
        c_emb = self.class_embed(labels)
        input = torch.cat([x, c_emb], dim=1)
        return self.net(input)


class CGANTrainer:
    def __init__(self, feature_dim: int = 11, num_classes: int = 6, device: str = "cpu"):
        self.device = device
        self.generator = CGANGenerator(feature_dim=feature_dim, num_classes=num_classes).to(device)
        self.discriminator = CGANDiscriminator(feature_dim=feature_dim, num_classes=num_classes).to(device)
    
    def train(self, X: np.ndarray, y: np.ndarray, epochs: int = 30):
        opt_g = optim.Adam(self.generator.parameters(), lr=0.0002)
        opt_d = optim.Adam(self.discriminator.parameters(), lr=0.0002)
        criterion = nn.BCEWithLogitsLoss()
        X_t = torch.FloatTensor(X).to(self.device)
        y_t = torch.LongTensor(y).to(self.device)
        
        for epoch in range(epochs):
            # Train discriminator
            z = torch.randn(len(X), 10).to(self.device)
            fake = self.generator(z, y_t)
            real_pred = self.discriminator(X_t, y_t)
            fake_pred = self.discriminator(fake.detach(), y_t)
            d_loss = criterion(real_pred, torch.ones_like(real_pred)) + criterion(fake_pred, torch.zeros_like(fake_pred))
            opt_d.zero_grad()
            d_loss.backward()
            opt_d.step()
            
            # Train generator
            fake_pred = self.discriminator(fake, y_t)
            g_loss = criterion(fake_pred, torch.ones_like(fake_pred))
            opt_g.zero_grad()
            g_loss.backward()
            opt_g.step()
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}, D_loss: {d_loss.item():.3f}, G_loss: {g_loss.item():.3f}")
    
    def generate(self, n_samples: int, labels: np.ndarray) -> np.ndarray:
        z = torch.randn(n_samples, 10).to(self.device)
        labels_t = torch.LongTensor(labels).to(self.device)
        with torch.no_grad():
            fake = self.generator(z, labels_t)
        return fake.cpu().numpy()


class TabularDiffusion:
    def __init__(self, feature_dim: int = 11, num_steps: int = 100, device: str = "cpu"):
        self.feature_dim = feature_dim
        self.num_steps = num_steps
        self.device = device
        self.betas = torch.linspace(1e-4, 0.02, num_steps).to(device)
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
        self.noise_pred = nn.Sequential(
            nn.Linear(feature_dim + 1, 128),
            nn.ReLU(),
            nn.Linear(128, feature_dim)
        ).to(device)
    
    def train(self, X: np.ndarray, epochs: int = 20):
        X_t = torch.FloatTensor(X).to(self.device)
        opt = optim.Adam(self.noise_pred.parameters(), lr=1e-4)
        for epoch in range(epochs):
            t = torch.randint(0, self.num_steps, (len(X),)).to(self.device)
            noise = torch.randn_like(X_t)
            alpha_t = self.alphas_cumprod[t].unsqueeze(1)
            x_t = torch.sqrt(alpha_t) * X_t + torch.sqrt(1 - alpha_t) * noise
            t_emb = t.float() / self.num_steps
            pred = self.noise_pred(torch.cat([x_t, t_emb.unsqueeze(1)], dim=1))
            loss = nn.MSELoss()(pred, noise)
            opt.zero_grad()
            loss.backward()
            opt.step()
    
    def sample(self, n_samples: int) -> np.ndarray:
        x = torch.randn(n_samples, self.feature_dim).to(self.device)
        for t in reversed(range(self.num_steps)):
            t_emb = torch.full((n_samples, 1), t / self.num_steps, device=self.device)
            pred_noise = self.noise_pred(torch.cat([x, t_emb], dim=1))
            alpha_t = self.alphas[t]
            x = (x - (1 - alpha_t) * pred_noise / torch.sqrt(self.alphas_cumprod[t])) / torch.sqrt(alpha_t)
        return x.cpu().numpy()


if __name__ == "__main__":
    trainer = CGANTrainer()
    # Example usage
    logger.info("AEGIS CGAN ready")

