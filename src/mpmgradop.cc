#include "tensorflow/core/framework/op_kernel.h"
#include "tensorflow/core/framework/tensor_shape.h"
#include "tensorflow/core/platform/default/logging.h"
#include "tensorflow/core/framework/shape_inference.h"

using namespace tensorflow;

REGISTER_OP("MpmGrad")
  .Input("position: float")               //(batch_size, dim, particles)
  .Input("velocity: float")               //(batch_size, dim, particles)
  .Input("affine: float")                 //(batch_size, dim, dim, particles)
  .Input("deformation: float")            //(batch_size, dim, dim, particles)
  .Input("actuation: float")              //(batch_size, dim, dim, particles
  .Input("position_out: float")           //(batch_size, dim, particles)
  .Input("velocity_out: float")           //(batch_size, dim, particles) 
  .Input("affine_out: float")             //(batch_size, dim, dim, particles) 
  .Input("deformation_out: float")        //(batch_size, dim, dim, particles)
  .Input("poly_out: float")               //(batch_size, dim, dim, particles)
  .Input("grid_out: float")               //(batch_size, dim + 1, num_cells)
  .Input("position_out_grad: float")      //(batch_size, dim, particles) 
  .Input("velocity_out_grad: float")      //(batch_size, dim, particles) 
  .Input("affine_out_grad: float")        //(batch_size, dim, dim, particles) 
  .Input("deformation_out_grad: float")   //(batch_size, dim, dim, particles) 
  .Input("poly_out_grad: float")          //(batch_size, dim, dim, particles)
  .Input("grid_out_grad: float")          //(batch_size, dim + 1, num_cells)
  .Attr("dt: float")
  .Attr("dx: float")
  .Attr("E: float")
  .Attr("nu: float")
  .Attr("m_p: float")
  .Attr("V_p: float")
  .Attr("gravity: list(float)")
  .Attr("resolution: list(int)")
  .Output("position_grad: float")         //(batch_size, dim, particles)
  .Output("velocity_grad: float")         //(batch_size, dim, particles)
  .Output("affine_grad: float")           //(batch_size, dim, dim, particles)
  .Output("deformation_grad: float")      //(batch_size, dim, dim, particles)
  .Output("actuation_grad: float");       //(batch_size, dim, dim, particles)


void MPMGradKernelLauncher(
    int dim, int *res, int num_particles, float dx, float dt, float E, float nu,
    float m_p, float V_p,
    float *gravity,
    const float *inx, const float *inv, const float *inF, const float *inC,
    const float *inA,
    const float *outx, const float *outv, const float *outF, const float *outC,
    const float *outP, const float *outgrid,
    float *grad_inx, float *grad_inv, float *grad_inF, float *grad_inC,
    float *grad_inA,
    const float *grad_outx, const float *grad_outv, 
    const float *grad_outF, const float *grad_outC,
    const float *grad_outP, const float *grad_outgrid);

class MPMGradOpGPU : public OpKernel {
 private:
  float dt_;
  float dx_;
  float E_, nu_, m_p_, V_p_;
  std::vector<float> gravity_;
  std::vector<int> res_;
 public:
  explicit MPMGradOpGPU(OpKernelConstruction* context) : OpKernel(context) {
    OP_REQUIRES_OK(context,
                   context->GetAttr("dt", &dt_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("dx", &dx_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("E", &E_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("nu", &nu_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("m_p", &m_p_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("V_p", &V_p_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("gravity", &gravity_));
    OP_REQUIRES_OK(context,
                   context->GetAttr("resolution", &res_));
  }
  
  void Compute(OpKernelContext* context) override {
    //printf("MPMOpGPU\n");

    // get the x
    const Tensor& inx = context->input(0);
    const Tensor& inv = context->input(1);
    const Tensor& inF = context->input(2);
    const Tensor& inC = context->input(3);
    const Tensor& inA = context->input(4);
    const Tensor& outx = context->input(5);
    const Tensor& outv = context->input(6);
    const Tensor& outF = context->input(7);
    const Tensor& outC = context->input(8);
    const Tensor& outP = context->input(9);
    const Tensor& outgrid = context->input(10);
    const Tensor& grad_outx = context->input(11);
    const Tensor& grad_outv = context->input(12);
    const Tensor& grad_outF = context->input(13);
    const Tensor& grad_outC = context->input(14);
    const Tensor& grad_outP = context->input(15);
    const Tensor& grad_outgrid = context->input(16);

    const TensorShape& x_shape = inx.shape();
    const TensorShape& v_shape = inv.shape();
    const TensorShape& F_shape = inF.shape();
    const TensorShape& C_shape = inC.shape();
    const TensorShape& A_shape = inA.shape();

    const int particles = x_shape.dim_size(2);

    const int dim = x_shape.dim_size(1);
    int res[dim];
    float gravity[dim];
    int num_cells = 1;
    for (int i = 0; i < dim; i++) {
      res[i] = res_[i];
      num_cells *= res[i];
      gravity[i] = gravity_[i];
    }

    // create output tensor
    Tensor* grad_inx= NULL;
    Tensor* grad_inv= NULL;
    Tensor* grad_inF= NULL;
    Tensor* grad_inC= NULL;
    Tensor* grad_inA= NULL;
    OP_REQUIRES_OK(context, context->allocate_output(0, x_shape, &grad_inx));
    OP_REQUIRES_OK(context, context->allocate_output(1, v_shape, &grad_inv));
    OP_REQUIRES_OK(context, context->allocate_output(2, F_shape, &grad_inF));
    OP_REQUIRES_OK(context, context->allocate_output(3, C_shape, &grad_inC));
    OP_REQUIRES_OK(context, context->allocate_output(4, A_shape, &grad_inA));

    auto f_inx = inx.flat<float>();
    auto f_inv = inv.flat<float>();
    auto f_inF = inF.flat<float>();
    auto f_inC = inC.flat<float>();
    auto f_inA = inA.flat<float>();
    auto f_outx = outx.flat<float>();
    auto f_outv = outv.flat<float>();
    auto f_outF = outF.flat<float>();
    auto f_outC = outC.flat<float>();
    auto f_outP = outP.flat<float>();
    auto f_outgrid = outgrid.flat<float>();
    auto f_grad_outx = grad_outx.flat<float>();
    auto f_grad_outv = grad_outv.flat<float>();
    auto f_grad_outF = grad_outF.flat<float>();
    auto f_grad_outC = grad_outC.flat<float>();
    auto f_grad_outP = grad_outP.flat<float>();
    auto f_grad_outgrid = grad_outgrid.flat<float>();
    auto f_grad_inx = grad_inx->template flat<float>();
    auto f_grad_inv = grad_inv->template flat<float>();
    auto f_grad_inF = grad_inF->template flat<float>();
    auto f_grad_inC = grad_inC->template flat<float>();
    auto f_grad_inA = grad_inA->template flat<float>();


    MPMGradKernelLauncher(dim, res, particles, dx_, dt_, E_, nu_, m_p_, V_p_, gravity,
        f_inx.data(), f_inv.data(), f_inF.data(), f_inC.data(), f_inA.data(),
        f_outx.data(), f_outv.data(), f_outF.data(), f_outC.data(),
        f_outP.data(), f_outgrid.data(),
        f_grad_inx.data(), f_grad_inv.data(),
        f_grad_inF.data(), f_grad_inC.data(),
        f_grad_inA.data(),
        f_grad_outx.data(), f_grad_outv.data(),
        f_grad_outF.data(), f_grad_outC.data(),
        f_grad_outP.data(), f_grad_outgrid.data());
  }
};

REGISTER_KERNEL_BUILDER(Name("MpmGrad").Device(DEVICE_GPU), MPMGradOpGPU);
