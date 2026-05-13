// Moved from Playwright suite: Mocha/Chai API test
const { expect } = require('chai');
const request = require('supertest');
const app = require('../../backend/app'); // Adjust the path as necessary

describe('Authentication Tests', () => {
    const userTypes = [
        { username: 'adminUser', password: 'adminPass', role: 'admin' },
        { username: 'regularUser', password: 'userPass', role: 'user' }
    ];

    userTypes.forEach(user => {
        describe(`${user.role} Authentication`, () => {
            it('should authenticate successfully', async () => {
                const res = await request(app)
                    .post('/auth/login')
                    .send({ username: user.username, password: user.password });
                expect(res.status).to.equal(200);
                expect(res.body).to.have.property('token');
            });

            it('should fail with incorrect password', async () => {
                const res = await request(app)
                    .post('/auth/login')
                    .send({ username: user.username, password: 'wrongPassword' });
                expect(res.status).to.equal(401);
            });

            it('should fail with non-existent user', async () => {
                const res = await request(app)
                    .post('/auth/login')
                    .send({ username: 'nonExistentUser', password: 'somePassword' });
                expect(res.status).to.equal(404);
            });
        });
    });
});
